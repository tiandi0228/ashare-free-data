"""Archived real-feature screening cannot generate executable trades."""
import copy
import unittest
from collector.p2_real_archive_research_screen import screen

def fixture():
    return {
      "phase":"P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY",
      "status":"PAGED_REAL_ARCHIVE_RESEARCH_ONLY",
      "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
      "actionable_buy_signals":[],"historical_PIT_verified":False,
      "full_market_universe_verified":False,
      "source_epoch_sha256":"a"*64,"archive_commit_sha":"b"*40,
      "asof_completed_day":"2026-10-20","page_index":2,
      "selected_shards":["shard_0016"],"scoped_verified_issuers":3,
      "computed_feature_issuers":2,"missing_feature_evidence_issuers":1,
      "features":[
        {"issuer":"sh.600000","asof_completed_day":"2026-10-20",
         "source_original_sha256":"c"*64,"last_close_cny":"10.50",
         "ma20_close_cny":"10.0000","above_ma20":True,
         "volume_vs_prior20_ratio":"2.0000",
         "trailing20_close_drawdown_pct":"0.0000","sector":None,
         "historical_st_and_company_actions_verified":False,"buy_signal":False},
        {"issuer":"sz.002249","asof_completed_day":"2026-10-20",
         "source_original_sha256":"d"*64,"last_close_cny":"9.00",
         "ma20_close_cny":"10.0000","above_ma20":False,
         "volume_vs_prior20_ratio":"0.5000",
         "trailing20_close_drawdown_pct":"10.0000","sector":None,
         "historical_st_and_company_actions_verified":False,"buy_signal":False}],
      "evidence_gaps":[{"issuer":"sh.600001","reason":"MISSING_EXACT_ASOF_CLOSE"}]}

class ArchivedResearchScreenTests(unittest.TestCase):
    def test_descriptive_order_is_non_executable_and_source_pinned(self):
        r=screen(fixture())
        self.assertEqual(r["status"],"DESCRIPTIVE_ARCHIVED_SAMPLE_ONLY")
        self.assertEqual([x["issuer"] for x in r["descriptive_order"]],
                         ["sh.600000","sz.002249"])
        self.assertEqual(r["ranked_observations"],2)
        self.assertEqual(r["source_gap_count"],1)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["actionable_buy_signals"],[])
        self.assertFalse(r["historical_OOS_validated"])
        self.assertFalse(r["complete_mainboard_coverage"])
        self.assertTrue(all(x["buy_signal"] is False for x in r["descriptive_order"]))
    def test_unsourced_or_incomplete_report_rejected(self):
        for field,val in (
           ("trade_gate","OPEN"),("orders",[{"side":"BUY"}]),
           ("archive_commit_sha","unverified"),
           ("scoped_verified_issuers",5),
           ("computed_feature_issuers",3),
           ("historical_PIT_verified",True),
           ("full_market_universe_verified",True)):
            p=fixture();p[field]=val
            with self.subTest(field=field):
                r=screen(p)
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_future_or_mismatched_source_evidence_rejected(self):
        for key,value in (
          ("asof_completed_day","2026-10-21"),
          ("source_original_sha256","missing"),
          ("last_close_cny","NaN"),
          ("ma20_close_cny","0"),
          ("volume_vs_prior20_ratio","-1"),
          ("trailing20_close_drawdown_pct","101"),
          ("above_ma20",False),
          ("sector","电力"),
          ("buy_signal",True),
          ("historical_st_and_company_actions_verified",True)):
            p=fixture();p["features"][0][key]=value
            with self.subTest(key=key):
                self.assertEqual(screen(p)["status"],"REJECTED")
    def test_duplicate_issuer_and_wrong_board_rejected(self):
        p=fixture();p["features"][1]["issuer"]="sh.600000"
        self.assertEqual(screen(p)["status"],"REJECTED")
        p=fixture();p["features"][0]["issuer"]="sz.300015"
        self.assertEqual(screen(p)["status"],"REJECTED")
    def test_missing_gap_evidence_or_oversized_page_rejected(self):
        p=fixture();p["evidence_gaps"]=[]
        self.assertEqual(screen(p)["status"],"REJECTED")
        p=fixture();p["features"]=p["features"]*70
        self.assertEqual(screen(p)["status"],"REJECTED")
if __name__=="__main__":unittest.main()
