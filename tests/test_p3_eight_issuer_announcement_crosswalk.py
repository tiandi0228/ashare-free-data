"""Eight P3 disclosure references cannot silently promote PIT or source gaps."""
import copy,json,unittest
from pathlib import Path
from collector.p3_eight_issuer_announcement_crosswalk import reconcile,EXPECTED,EPOCH

ROOT=Path(__file__).resolve().parents[1]
def fixture():
    refs=json.loads((ROOT/"evidence/p3_eight_issuer_halt_resume_research_refs_20261112.json").read_text())
    queue={"phase":"P2_P3_LIVE_FEATURE_GAP_AND_ISSUER_DISCLOSURE_RESEARCH_QUEUE",
      "source_epoch_sha256":EPOCH,"missing_p3_halt_source_reference_issuer_count":8,
      "curated_p3_reference_issuer_count":7,"unresolved_gap_issuers":16,
      "trade_gate":"BLOCKED","historical_PIT_verified":False,
      "orders":[],"executable_candidates":[],
      "missing_official_halt_source_research_queue":[
       {"issuer":issuer,"shard_id":s,"original_csv_sha256":h}
       for issuer,(s,h,*_) in EXPECTED.items()]}
    return [queue,refs]

class IssuerDisclosureTests(unittest.TestCase):
    def setUp(self):self.args=fixture()
    def audit(self):return reconcile(*self.args)
    def reject(self):
        with self.assertRaises(ValueError):self.audit()
    def test_eight_links_retained_no_pit_promotion(self):
        r=self.audit()
        self.assertEqual(r["research_issuer_reference_count"],8)
        self.assertEqual(r["combined_research_reference_issuer_count"],15)
        self.assertEqual(r["still_missing_a_research_link_issuer_count"],0)
        self.assertEqual(r["original_feature_gap_issuers_unresolved"],16)
        self.assertEqual(r["original_feature_gap_shards_unresolved"],15)
        self.assertEqual(r["P2_feature_shards_promoted"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["pdf_original_bytes_sha_independently_verified_count"],0)
    def test_all_eight_original_csv_sha_bound(self):
        self.args[0]["missing_official_halt_source_research_queue"][0]["original_csv_sha256"]="f"*64
        self.reject()
    def test_duplicate_case_rejected(self):
        self.args[1]["cases"][1]["issuer"]=self.args[1]["cases"][0]["issuer"]
        self.reject()
    def test_fake_pdf_sha_rejected(self):
        self.args[1]["cases"][0]["documents"][0]["content_sha256"]="a"*64
        self.reject()
    def test_unauthenticated_publication_instant_rejected(self):
        self.args[1]["cases"][0]["documents"][0]["first_publication_instant_authenticated"]=True
        self.reject()
    def test_historical_st_effective_day_guard(self):
        self.args[1]["cases"][3]["st_removal_effective_day"]=None
        self.reject()
    def test_historical_st_warning_guard(self):
        self.args[1]["cases"][5]["unresolved_caveat"]=None
        self.reject()
    def test_bad_reprint_host_rejected(self):
        self.args[1]["cases"][2]["documents"][0]["url"]="https://unknown.invalid/reprint"
        self.reject()
    def test_fake_original_pdf_host_rejected(self):
        self.args[1]["cases"][0]["documents"][0]["url"]="https://attacker.invalid/a.PDF"
        self.reject()
    def test_gap_promotion_rejected(self):
        self.args[1]["cases"][0]["gap_resolved"]=True
        self.reject()
    def test_trade_gate_not_overrideable(self):
        self.args[1]["trade_gate"]="OPEN"
        self.reject()
    def test_vendor_date_mismatch_rejected(self):
        self.args[1]["cases"][0]["claimed_halt_start"]="2026-09-15"
        self.reject()
    def test_missing_live_case_rejected(self):
        self.args[0]["missing_official_halt_source_research_queue"].pop()
        self.reject()
