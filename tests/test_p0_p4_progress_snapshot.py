"""Progress presentation must not turn missing evidence into a regression or a passing gate."""
import copy
import unittest
from collector.p0_p4_progress_snapshot import summarize

SHA = "a"*40

def baseline(tested, passed=False):
    stages = {}
    for phase in ("P2", "P3", "P4"):
        rows = []
        for index in range(10):
            ok = tested and passed and index == 0
            rows.append({"id": "criterion_"+str(index), "passed": ok,
                         "evidence": {"source_commit": SHA, "verification": "OFFLINE_UNITTEST_PASSED_IN_THIS_RUN"} if ok else None})
        stages[phase] = {"total_weight": 100, "criteria": rows,
                         "engineering_acceptance_baseline_pct": 10 if tested else None}
    return {"trade_gate": "BLOCKED", "source_commit": SHA,
            "tests_executed": tested, "stages": stages}

class ProgressSnapshotTests(unittest.TestCase):
    def test_missing_rerun_does_not_erase_historical_tests(self):
        result = summarize(baseline(False), baseline(True, True))
        self.assertEqual(result["stages"]["P2"]["historically_observed_test_criteria_count"], 1)
        self.assertIsNone(result["stages"]["P2"]["current_offline_acceptance_pct"])
        self.assertEqual(result["stages"]["P2"]["verification"], "NOT_RERUN")
        self.assertIsNone(result["stages"]["P2"]["development_pct"])
        self.assertFalse(result["production_ready"])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_p1_epoch_kept_separate(self):
        p1 = {"phase": "P1_DURABLE_PINNED_PROGRESS", "trade_gate": "BLOCKED",
              "historical_PIT_verified": False,
              "status": "VERIFIED_DURABLE_LEDGER_NOT_MARKET_CERTIFICATION",
              "completed_shards": 197, "total_shards": 400, "source_sha256": "b"*64}
        result = summarize(baseline(False), p1=p1)
        self.assertEqual(result["stages"]["P1"]["research_shard_coverage_pct"], 49.25)
        self.assertIsNone(result["stages"]["P1"]["development_pct"])

    def test_rejects_unproven_success(self):
        b = baseline(True, True)
        b["stages"]["P2"]["criteria"][0]["evidence"]["source_commit"] = "b"*40
        with self.assertRaises(ValueError):
            summarize(b)

    def test_rejects_unsafe_current(self):
        b = baseline(False)
        b["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            summarize(b)

if __name__ == "__main__":
    unittest.main()
