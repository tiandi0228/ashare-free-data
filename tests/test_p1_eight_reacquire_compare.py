"""Fail-closed independent recapture comparator tests (synthetic receipts)."""
import copy
import unittest
from collector.p1_eight_reacquire_compare import compare

def receipt(run):
    codes=[f"sh.{600190+i:06d}" for i in range(8)]
    return {"phase":"P1_BOUNDED_VENDOR_EARLY_ONLY_HINDSIGHT_RESEARCH_HISTORY",
            "capture_run_id":run,"issuer_codes":codes,
            "source_observed_issuers":8,"logical_source_queries":8,"source_observed_rows":80,
            "trade_gate":"BLOCKED","orders":[],"official_historical_PIT_universe_verified":False,
            "results":[{"code":c,"status":"VENDOR_HISTORY_OBSERVED_NOT_PIT",
                        "original_source_sha256":format(i+1,"064x"),"original_source_rows":10,
                        "vendor_trade_status_1_rows":9,"vendor_trade_status_0_rows":1}
                       for i,c in enumerate(codes)]}

class RecaptureTests(unittest.TestCase):
    def test_independent_matching_captures_remain_research(self):
        r=compare(receipt(1),receipt(2))
        self.assertEqual(r["matching_issuers"],8)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["official_historical_PIT_universe_verified"])

    def test_same_run_rejected(self):
        with self.assertRaisesRegex(ValueError,"independent"):
            compare(receipt(1),receipt(1))

    def test_changed_bytes_flagged(self):
        b=receipt(2);b["results"][0]["original_source_sha256"]="f"*64
        self.assertEqual(compare(receipt(1),b)["matching_issuers"],7)

    def test_wrong_cohort_rejected(self):
        b=receipt(2);b["issuer_codes"][0]="sh.601000";b["results"][0]["code"]="sh.601000"
        with self.assertRaisesRegex(ValueError,"different cohorts"):
            compare(receipt(1),b)

    def test_incomplete_rows_rejected(self):
        b=receipt(2);b["results"][0]["original_source_rows"]=11
        with self.assertRaisesRegex(ValueError,"row conservation"):
            compare(receipt(1),b)

    def test_trade_gate_must_stay_blocked(self):
        b=receipt(2);b["trade_gate"]="OPEN"
        with self.assertRaisesRegex(ValueError,"unsafe"):
            compare(receipt(1),b)

if __name__=="__main__":
    unittest.main()
