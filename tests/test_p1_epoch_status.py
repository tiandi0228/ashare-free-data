"""Prevent false progress by summing unrelated P1 roster epochs."""
import unittest
from collector.p1_epoch_status import summarize

A = "a" * 64
B = "b" * 64
D = "c" * 64

def ledger(sha, indexes):
    completed = [
        {"index": i, "issuer_count": 8, "manifest_sha256": D,
         "receipt_sha256": D} for i in indexes
    ]
    remaining = [i for i in range(400) if i not in indexes]
    return {
        "phase": "P1_ROSTER_SHARD_LEDGER",
        "source_sha256": sha, "shard_count": 400,
        "completed": completed, "completed_shards": len(completed),
        "completed_issuers": 8 * len(completed),
        "pending_shards": remaining,
        "failed_in_this_reconciliation": [],
        "next_shard": remaining[0] if remaining else None,
        "full_market_bars_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [],
        "executable_candidates": [],
    }


class EpochStatusTests(unittest.TestCase):
    def test_disjoint_epoch_counts_not_added_or_chosen_active(self):
        report = summarize({B: ledger(B, range(163)), A: ledger(A, range(44))})
        self.assertEqual([r["completed_shards"] for r in report["epochs"]], [44, 163])
        self.assertIsNone(report["combined_completed_shards"])
        self.assertIsNone(report["combined_coverage_percent"])
        self.assertIsNone(report["approved_active_source_sha256"])
        self.assertFalse(report["cross_epoch_merge_authorized"])
        self.assertFalse(report["full_market_bars_certified"])
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertEqual(report["orders"], [])

    def test_rejects_misfiled_epoch_and_unsafe_promotion(self):
        bad = ledger(A, [0])
        with self.assertRaises(ValueError):
            summarize({B: bad})
        bad["source_sha256"] = B
        bad["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            summarize({B: bad})

    def test_empty_directory_does_not_imply_completion(self):
        report = summarize({})
        self.assertEqual(report["epochs"], [])
        self.assertIsNone(report["combined_coverage_percent"])
        self.assertFalse(report["historical_PIT_verified"])


if __name__ == "__main__":
    unittest.main()
