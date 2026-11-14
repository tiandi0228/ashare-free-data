"""Fail-closed synthetic regression tests; no remote data or trading."""
import copy
import json
import unittest
from pathlib import Path
from collector.progress_nonadditive_audit import reconcile

ROOT = Path(__file__).resolve().parents[1]
class ProgressLedgerNonadditiveTests(unittest.TestCase):
    def setUp(self):
        self.p1 = {"phase": "P1_ROSTER_SHARD_LEDGER", "completed_shards": 2,
                   "shard_count": 400, "source_sha256": "a"*64,
                   "completed": [{"index": 0}, {"index": 1}]}
        self.history = [{"kind": "PREVIOUSLY_REPORTED_NOT_REPLAYED_THIS_RUN",
                         "reported_day": "2026-11-11", "feature_complete_shards": 215,
                         "observed_shards": 227}]
    def test_separate_counters_never_added(self):
        out = reconcile(self.p1, self.history)
        self.assertIsNone(out["combined_shards"])
        self.assertIsNone(out["overall_completion_pct"])
        self.assertIsNone(out["P2"]["current_feature_coverage_verified"])
        self.assertFalse(out["P1"]["archive_completed_verified"])
        self.assertFalse(out["historical_PIT_verified"])
        self.assertEqual(out["trade_gate"], "BLOCKED")
        self.assertEqual(out["orders"], [])
        self.assertEqual(out["executable_candidates"], [])
    def test_duplicate_p1_index_rejected(self):
        bad = copy.deepcopy(self.p1)
        bad["completed"][1]["index"] = 0
        with self.assertRaises(ValueError): reconcile(bad, self.history)
    def test_forged_verified_p2_rejected(self):
        bad = copy.deepcopy(self.history)
        bad[0]["kind"] = "CURRENT_ORIGINAL_REPLAY_VERIFIED"
        with self.assertRaises(ValueError): reconcile(self.p1, bad)
    def test_invalid_p2_count_rejected(self):
        bad = copy.deepcopy(self.history)
        bad[0]["feature_complete_shards"] = 228
        with self.assertRaises(ValueError): reconcile(self.p1, bad)
    def test_invalid_p1_count_rejected(self):
        bad = copy.deepcopy(self.p1)
        bad["completed_shards"] = 3
        with self.assertRaises(ValueError): reconcile(bad, self.history)
    def test_actual_main_checkpoint_is_44_of_400(self):
        checkpoint = json.loads((ROOT/"evidence/p1_checkpoint.json").read_text())
        history = json.loads((ROOT/"evidence/progress_p2_historical_unreplayed_20261112.json").read_text())
        out = reconcile(checkpoint, history)
        self.assertEqual(out["P1"]["research_roster_checkpoint"], 44)
        self.assertEqual(out["P1"]["denominator"], 400)
        self.assertEqual(out["P2"]["reported_history"][-1]["feature_complete_shards"], 215)
        self.assertIsNone(out["combined_shards"])
if __name__ == "__main__":
    unittest.main()
