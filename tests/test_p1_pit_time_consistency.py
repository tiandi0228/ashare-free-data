"""Point-in-time structural regressions must fail closed for future information."""
import copy,unittest
from collector.p1_pit_time_consistency import audit
def sample():
    return {"decision_at":"2026-10-30T14:30:00+08:00","observations":[{
       "code":"002249","field":"st_status",
       "observed_at":"2026-10-29T15:00:00+08:00",
       "published_at":"2026-10-29T19:00:00+08:00",
       "available_at":"2026-10-30T08:00:00+08:00",
       "effective_from":"2026-10-29T00:00:00+08:00",
       "effective_to":None,
       "original_source_sha256":"a"*64,"source_archived":True}]}
class PitStructuralTests(unittest.TestCase):
    def test_valid_structure_never_authenticates_pit_or_trades(self):
        r=audit(sample())
        self.assertEqual(r["status"],"STRUCTURAL_CHECK_PASSED_PIT_UNVERIFIED")
        self.assertFalse(r["historical_PIT_verified"])
        self.assertFalse(r["full_market_bars_certified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_future_disclosure_rejected(self):
        x=sample();x["observations"][0]["published_at"]="2026-10-31T19:00:00+08:00"
        self.assertEqual(audit(x)["status"],"REJECTED")
    def test_future_effective_status_rejected(self):
        x=sample();x["observations"][0]["effective_from"]="2026-11-03T00:00:00+08:00"
        self.assertIn("ROW_0_NOT_EFFECTIVE_AT_DECISION",audit(x)["issues"])
    def test_expired_status_rejected(self):
        x=sample();x["observations"][0]["effective_to"]="2026-10-30T09:00:00+08:00"
        self.assertEqual(audit(x)["status"],"REJECTED")
    def test_naive_timestamp_rejected(self):
        x=sample();x["decision_at"]="2026-10-30T14:30:00"
        self.assertIn("INVALID_DECISION_TIMESTAMP",audit(x)["issues"])
    def test_duplicates_and_missing_source_block(self):
        x=sample();x["observations"].append(copy.deepcopy(x["observations"][0]))
        self.assertEqual(audit(x)["status"],"REJECTED")
        y=sample();y["observations"][0]["source_archived"]=False
        self.assertIn("ROW_0_SOURCE_ARCHIVE_NOT_CONFIRMED",audit(y)["issues"])
        z=sample();z["observations"][0]["original_source_sha256"]="none"
        self.assertIn("ROW_0_ORIGINAL_EVIDENCE_HASH_MISSING",audit(z)["issues"])
    def test_missing_facts_do_not_pass(self):
        for value in (None,{},{"decision_at":"2026-10-30T14:30:00+08:00","observations":[]}):
            self.assertEqual(audit(value)["status"],"REJECTED")
if __name__=="__main__":unittest.main()
