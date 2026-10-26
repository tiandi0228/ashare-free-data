import hashlib,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from collector.p3_official_original_archive import prepare,verify_archive

ISSUER="sh.600038";NOTICE="123456789"
URL=f"https://static.cninfo.com.cn/finalpage/2026-10-19/{NOTICE}.PDF"
PDF=b"%PDF-1.7\n"+b"x"*3100

class ArchiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/"observed";self.source.mkdir()
        (self.source/"sh_600038_123456789.pdf").write_bytes(PDF)
        self.digest=hashlib.sha256(PDF).hexdigest()
        self.receipts={"phase":"P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE",
            "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
            "historical_first_publication_authenticated":False,
            "retrieved":1,"sources":[{
                "issuer":ISSUER,"announcement_id":NOTICE,"url":URL,
                "original_bytes_verified":True,"original_file":"sh_600038_123456789.pdf",
                "sha256":self.digest,"historical_first_publication_authenticated":False,
                "observed_at_utc":"2026-10-26T03:30:00+00:00"}]}
        self.queue={"phase":"P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST",
            "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
            "roster_source_sha256":"b"*64,"completed_issuers_replayed":384,
            "required_official_evidence_cells":3416,
            "official_evidence_tasks":[{"issuer":ISSUER,"decision_day":"2026-10-20",
            "status_kind":"halt","historical_asof_verified":False,
            "vendor_csv_sha256":"a"*64,"source_shard":44,
            "vendor_tradestatus_observed":"0"}]}
        self.index={"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY",
            "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
            "results":[{"issuer":ISSUER,"candidates":[{
                "announcement_id":NOTICE,"official_pdf_url":URL,
                "announcement_title_unverified":"关于停牌的公告",
                "index_published_milliseconds_unverified":1792560000000}]}]}
        self.review={"phase":"P3_P1_ORIGINAL_EFFECTIVE_CLAUSE_REVIEW",
            "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
            "official_PIT_cells_certified":0,"certified_effective_dates":0,
            "authenticated_first_publication_times":0,
            "evaluated_research_links":1,
            "explicit_original_clause_candidates":1,
            "manual_review_only":[{
                "issuer":ISSUER,"announcement_id":NOTICE,
                "decision_day":"2026-10-20","candidate_kind":"halt",
                "original_pdf_sha256":self.digest,
                "source_date_text":"2026年10月20日",
                "local_textual_direction_candidate":"HALT_START",
                "clause_excerpt":"公司股票自2026年10月20日起停牌",
                "historical_asof_usable":False,
                "historical_first_publication_authenticated":False,
                "historical_effective_date_authenticated":False,
                "complete_issuer_state_history_certified":False}]}
        self.write_receipts()
    def write_receipts(self):
        (self.source/"quality.json").write_text(json.dumps(self.receipts))
    def make(self):
        return prepare(originals_root=self.source,review=self.review,queue=self.queue,
                       index=self.index,run_id=42,upstream_run_id=41)
    def test_original_bytes_and_semantics_are_archived_as_uncertified(self):
        manifest,files=self.make()
        self.assertEqual(manifest["original_pdf_count"],1)
        self.assertEqual(len(files),1)
        self.assertEqual(manifest["explicit_local_textual_candidate_count"],1)
        claim=manifest["research_date_action_links"][0]
        self.assertEqual(claim["vendor_csv_sha256"],"a"*64)
        self.assertFalse(claim["first_publication_authenticated"])
        self.assertFalse(claim["decision_time_available_certified"])
        archive=self.root/"archive";archive.mkdir()
        (archive/"runs").mkdir()
        (archive/"runs/42.json").write_text(json.dumps(manifest))
        for path,data in files.items():
            target=archive/path;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
        checked=verify_archive(archive,42,source_root=self.source)
        self.assertEqual(checked["retrieved_and_persisted_originals"],1)
        self.assertFalse(checked["historical_PIT_verified"])
        (target).write_bytes(b"%PDF-different")
        with self.assertRaises(ValueError):verify_archive(archive,42)
    def test_mutated_original_is_rejected(self):
        (self.source/"sh_600038_123456789.pdf").write_bytes(PDF+b"z")
        with self.assertRaises(ValueError):self.make()
    def test_fake_publication_certification_rejected(self):
        self.receipts["sources"][0]["historical_first_publication_authenticated"]=True
        self.write_receipts()
        with self.assertRaises(ValueError):self.make()
    def test_forged_decision_time_clearance_rejected(self):
        self.review["manual_review_only"][0]["historical_asof_usable"]=True
        with self.assertRaises(ValueError):self.make()
    def test_pdf_receipt_not_in_official_index_rejected(self):
        self.index["results"][0]["candidates"][0]["official_pdf_url"]="https://example.org/a.pdf"
        with self.assertRaises(ValueError):self.make()
    def test_absent_P1_original_sha_rejected(self):
        self.queue["official_evidence_tasks"][0]["vendor_csv_sha256"]=None
        with self.assertRaises(ValueError):self.make()
    def test_missing_source_file_rejected(self):
        (self.source/"sh_600038_123456789.pdf").unlink()
        with self.assertRaises(FileNotFoundError):self.make()
    def test_missing_original_does_not_imply_safe_issuer(self):
        self.receipts["retrieved"]=0
        self.receipts["sources"][0].update(original_bytes_verified=False)
        self.write_receipts()
        self.review["evaluated_research_links"]=0
        self.review["explicit_original_clause_candidates"]=0
        self.review["manual_review_only"]=[]
        m,files=self.make()
        self.assertEqual(files,{})
        self.assertTrue(m["source_pdf_receipts"][0]["missing_original_is_not_no_risk"])
    def test_duplicate_clause_not_accepted(self):
        self.review["manual_review_only"]*=2
        self.review["evaluated_research_links"]=2
        self.review["explicit_original_clause_candidates"]=2
        with self.assertRaises(ValueError):self.make()
    def test_invalid_run_id_rejected(self):
        with self.assertRaises(ValueError):
            prepare(originals_root=self.source,review=self.review,queue=self.queue,
                    index=self.index,run_id=0,upstream_run_id=41)

if __name__=="__main__":unittest.main()
