"""Offline fail-closed tests for the explicit epoch coverage display."""
import unittest
from collector.p1_epoch_coverage_report import assess

SHA = "a" * 64


def fixture():
    return {
        "phase": "P1_ROSTER_SHARD_LEDGER",
        "source_sha256": SHA,
        "shard_count": 4,
        "completed": [{
            "index": 0,
            "issuer_count": 8,
            "manifest_sha256": "b" * 64,
            "receipt_sha256": "c" * 64,
        }],
        "completed_shards": 1,
        "completed_issuers": 8,
        "pending_shards": [1, 2, 3],
        "next_shard": 1,
        "failed_in_this_reconciliation": [],
        "full_market_bars_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


class TestEpochCoverage(unittest.TestCase):
    def test_safe_coverage_not_system_completion(self):
        report = assess(fixture(), SHA)
        self.assertEqual(report["historical_data_collection_percent"], 25)
        self.assertEqual(report["pending_shards"], 3)
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertFalse(report["historical_PIT_verified"])
        self.assertFalse(report["full_market_bars_certified"])

    def test_reject_wrong_epoch(self):
        with self.assertRaises(ValueError):
            assess(fixture(), "d" * 64)

    def test_reject_corrupt_count(self):
        row = fixture()
        row["completed_shards"] = 2
        with self.assertRaises(ValueError):
            assess(row, SHA)

    def test_reject_trade_promotion(self):
        row = fixture()
        row["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            assess(row, SHA)

    def test_reject_missing_explicit_sha(self):
        with self.assertRaises(ValueError):
            assess(fixture(), None)


if __name__ == "__main__":
    unittest.main()
