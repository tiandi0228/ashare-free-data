import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p3_halt_resume_pair_review import review
I="sh.600319"
HALT="a"*64
PDF=b"%PDF-1.7\n"+b"y"*3100
DIGEST=hashlib.sha256(PDF).hexdigest()
def episodes():
    return {"phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
      "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
      "official_PIT_cells_certified":0,"complete_issuer_halt_intervals_certified":False,
      "unpaired_halt_starts_needing_resumption_search":1,
      "official_resumption_followups":[{"issuer":I,
        "halt_text_date":"2025-11-04","original_pdf_sha256":HALT,
        "historical_halt_interval_certified":False}]}
class TestPairing(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);(self.root/"resume_runs").mkdir()
        path=self.root/f"pdf/sh_600319/1224811232/{DIGEST}.pdf"
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(PDF)
        self.path=path
        self.item={"issuer":I,"announcement_id":"1224811232",
           "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2025-11-18/1224811232.PDF",
           "source_halt_text_day":"2025-11-04","source_halt_original_sha256":HALT,
           "original_pdf_retrieved":True,"pdf_sha256":DIGEST,"bytes":len(PDF),
           "archival_pdf_path":f"pdf/sh_600319/1224811232/{DIGEST}.pdf",
           "actual_resumption_authenticated":False,
           "resume_same_clause_text_candidates":[{
              "pdf_date_phrase":"2025年11月18日",
              "original_sha256":DIGEST,
              "date_clause_unverified":"公司股票将于2025年11月18日开市起复牌",
              "first_publication_authenticated":False,"resumption_date_authenticated":False}]}
        self.manifest={"phase":"P3_RESUME_SOURCE_SHA_APPEND_ONLY_RESEARCH",
            "run_id":10,"trade_gate":"BLOCKED","orders":[],
            "historical_PIT_verified":False,"publisher_first_publication_authenticated":False,
            "official_resume_effective_dates_certified":0,
            "continuous_halt_resume_intervals_certified":0,
            "source_halt_issuers_attempted":1,
            "source_halt_records":[{"issuer":I,"source_halt_date":"2025-11-04",
                "source_halt_original_sha256":HALT,"historical_resume_authenticated":False}],
            "downloaded_resume_original_count":1,
            "resume_notice_source_receipts":[self.item]}
        self.save()
    def save(self,run=10):
        self.manifest["run_id"]=run
        (self.root/f"resume_runs/{run}.json").write_text(json.dumps(self.manifest))
    def test_pair_is_original_proven_but_not_PIT(self):
        result=review(episodes(),self.root)
        self.assertEqual(result["deduplicated_research_text_pairs"],1)
        self.assertEqual(result["unpaired_halt_sources_remaining_in_bounded_research"],0)
        self.assertEqual(result["text_only_halt_resume_pairs"][0]["resume_text_date"],"2025-11-18")
        self.assertEqual(result["official_halt_resume_intervals_certified"],0)
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_multiple_runs_same_notice_deduplicate(self):
        self.save(11)
        result=review(episodes(),self.root)
        self.assertEqual(result["archived_resume_runs_replayed"],2)
        self.assertEqual(result["deduplicated_research_text_pairs"],1)
        self.assertEqual(result["text_only_halt_resume_pairs"][0]["run_ids"],[10,11])
    def test_forged_prior_original_rejected(self):
        self.manifest["source_halt_records"][0]["source_halt_original_sha256"]="f"*64
        self.save()
        with self.assertRaises(ValueError):review(episodes(),self.root)
    def test_incorrect_original_SHA_rejected(self):
        self.path.write_bytes(b"changed")
        with self.assertRaises(ValueError):review(episodes(),self.root)
    def test_no_resume_clause_remains_unpaired(self):
        self.item["resume_same_clause_text_candidates"]=[]
        self.manifest["explicit_original_resume_text_candidates"]=0
        self.save()
        result=review(episodes(),self.root)
        self.assertEqual(result["deduplicated_research_text_pairs"],0)
        self.assertEqual(result["unpaired_halt_sources_remaining_in_bounded_research"],1)
    def test_text_date_before_halt_is_rejected(self):
        self.item["resume_same_clause_text_candidates"][0].update(
          pdf_date_phrase="2025年11月2日",date_clause_unverified="自2025年11月2日起复牌")
        self.save()
        result=review(episodes(),self.root)
        self.assertEqual(result["resume_text_before_halt_rejected"],1)
    def test_fake_first_publication_rejected(self):
        self.item["resume_same_clause_text_candidates"][0]["first_publication_authenticated"]=True
        self.save()
        with self.assertRaises(ValueError):review(episodes(),self.root)
if __name__=="__main__":unittest.main()
