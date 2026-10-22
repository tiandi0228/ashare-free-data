import copy
import unittest
from collector.p4_prospective_handoff import assess

class ProspectiveHandoffTests(unittest.TestCase):
    def setUp(self):
        self.index={"trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
                    "pagination_complete":True,"query_day_time_filter_verified":True,
                    "raw_wrong_day_timestamps":0,"raw_invalid_timestamps":0,
                    "sample_page_stability_rechecks":[{"page":1,"status":"MATCH"},{"page":2,"status":"MATCH"},{"page":3,"status":"MATCH"}],
                    "unique_raw_announcement_ids":90,"reported_total":90,"query_day":"2026-10-22"}
        self.candidate={"trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
                        "source_pagination_complete":True,"candidate_count":2}
        self.pdf={"trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
                  "candidates_available":2,"attempted":2,"successful":2,
                  "text_extracted_count":2,"text_extraction_failed_count":0}

    def run_assessment(self):
        return assess(self.index,self.candidate,self.pdf)

    def test_good_research_capture_still_blocks_trading(self):
        r=self.run_assessment()
        self.assertTrue(r["capture_checks_all_passed"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertFalse(r["official_historical_PIT_universe_verified"])
        self.assertFalse(r["frozen_out_of_sample_backtest_verified"])

    def test_wrong_day_does_not_pass(self):
        self.index["raw_wrong_day_timestamps"]=1
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_changed_middle_page_does_not_pass(self):
        self.index["sample_page_stability_rechecks"][1]["status"]="CHANGED"
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_missing_middle_page_does_not_pass(self):
        self.index["sample_page_stability_rechecks"]=self.index["sample_page_stability_rechecks"][:2]
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_id_mismatch_does_not_pass(self):
        self.index["unique_raw_announcement_ids"]=89
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_pdf_failure_does_not_pass(self):
        self.pdf["text_extracted_count"]=1
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_unlinked_candidate_does_not_pass(self):
        self.pdf["candidates_available"]=3
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_missing_source_timestamp_does_not_pass(self):
        self.index["query_day_time_filter_verified"]=False
        self.assertFalse(self.run_assessment()["capture_checks_all_passed"])

    def test_any_unblocked_input_raises(self):
        self.candidate["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):
            self.run_assessment()

    def test_nonempty_orders_raises(self):
        self.pdf["orders"]=[{"qty":100}]
        with self.assertRaises(ValueError):
            self.run_assessment()

if __name__=="__main__":
    unittest.main()
