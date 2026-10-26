import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p3_resume_original_archive import prepare,verify_persisted

ISSUER="sh.600319"
NOTICE="1222222222"
URL=f"https://static.cninfo.com.cn/finalpage/2025-11-07/{NOTICE}.PDF"
PDF=b"%PDF-1.7\n"+b"x"*3100
SHA=hashlib.sha256(PDF).hexdigest()

class OriginalResumeArchiveTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);self.docs=self.root/"docs";self.docs.mkdir()
        (self.docs/f"sh_600319_{NOTICE}.pdf").write_bytes(PDF)
        self.original={"phase":"P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE",
          "attempted":1,"retrieved":1,"trade_gate":"BLOCKED","orders":[],
          "historical_first_publication_authenticated":False,
          "historical_PIT_verified":False,
          "sources":[{"issuer":ISSUER,"announcement_id":NOTICE,"url":URL,
               "original_bytes_verified":True,
               "original_file":f"sh_600319_{NOTICE}.pdf",
               "sha256":SHA,"historical_PIT_verified":False,
               "historical_first_publication_authenticated":False,
               "observed_at_utc":"2026-10-26T04:00:00+00:00"}]}
        (self.docs/"quality.json").write_text(json.dumps(self.original))
        self.index={"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY",
          "purpose":"BOUNDED_ORIGINAL_PDF_RESUMPTION_FOLLOWUP_RESEARCH",
          "trade_gate":"BLOCKED","orders":[],
          "historical_PIT_verified":False,
          "complete_issuer_halt_intervals_certified":False,
          "attempted":1,
          "selected_halt_sources":[{"issuer":ISSUER,"source_halt_date":"2025-11-04",
             "source_halt_original_sha256":"b"*64,"source_halt_certified":False,
             "historical_resume_authenticated":False}],
          "results":[{"issuer":ISSUER,"status":"RESUMPTION_TITLE_RESEARCH_CANDIDATES_UNVERIFIED",
             "candidate_count":1,"candidates":[{"announcement_id":NOTICE,
               "official_pdf_url":URL,
               "announcement_title_unverified":"关于公司股票复牌的公告",
               "historical_PIT_verified":False}]}]}
        self.text={"phase":"P3_REAL_P1_PDF_TEXT_RESEARCH_CUES",
          "independently_replayed_originals":1,"source_count":1,
          "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],
          "sources":[{"issuer":ISSUER,"announcement_id":NOTICE,"original_sha256":SHA,
              "historical_PIT_verified":False,"issuer_code_in_text":True,
              "date_contexts_research_only":[{"date_text":"2025年11月7日",
                "source_text_context":"公司股票将于2025年11月7日起复牌。",
                "effective_date_certified":False}]}]}
    def make(self):
        return prepare(self.index,self.docs,self.text,40)
    def test_archive_two_independent_hashes_never_certifies_resume(self):
        manifest,files=self.make()
        self.assertEqual(manifest["explicit_original_resume_text_candidates"],1)
        self.assertEqual(len(files),1)
        archive=self.root/"repo";archive.mkdir();(archive/"resume_runs").mkdir()
        (archive/"resume_runs/40.json").write_text(json.dumps(manifest))
        for rel,data in files.items():
            path=archive/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        result=verify_persisted(archive,40)
        self.assertEqual(result["official_originals_sha_verified"],1)
        self.assertEqual(result["same_clause_resumption_text_candidates"],1)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        path.write_bytes(b"%PDF-corrupt")
        with self.assertRaises(ValueError):verify_persisted(archive,40)
    def test_fake_original_sha_fails(self):
        self.original["sources"][0]["sha256"]="f"*64
        (self.docs/"quality.json").write_text(json.dumps(self.original))
        with self.assertRaises(ValueError):self.make()
    def test_original_missing_not_positive(self):
        self.original["retrieved"]=0
        self.original["sources"][0]["original_bytes_verified"]=False
        (self.docs/"quality.json").write_text(json.dumps(self.original))
        (self.docs/f"sh_600319_{NOTICE}.pdf").unlink()
        self.text["independently_replayed_originals"]=0
        self.index["results"][0]["status"]="INDEX_UNAVAILABLE_NOT_NO_RESUMPTION"
        r,files=self.make()
        self.assertEqual(files,{})
        self.assertEqual(r["explicit_original_resume_text_candidates"],0)
    def test_index_original_issuer_mismatch_rejected(self):
        self.index["selected_halt_sources"][0]["issuer"]="sh.600303"
        with self.assertRaises(ValueError):self.make()
    def test_unauthenticated_date_does_not_get_certified(self):
        r,files=self.make()
        self.assertEqual(r["official_resume_effective_dates_certified"],0)
        self.assertFalse(r["publisher_first_publication_authenticated"])
    def test_wrong_historical_issuer_code_blocks_same_clause(self):
        self.text["sources"][0]["issuer_code_in_text"]=False
        r,files=self.make()
        self.assertEqual(r["explicit_original_resume_text_candidates"],0)
    def test_forbidden_prior_halt_pit_blocks(self):
        self.index["selected_halt_sources"][0]["historical_resume_authenticated"]=True
        with self.assertRaises(ValueError):self.make()
if __name__=="__main__":unittest.main()
