import unittest
from collector.p1_epoch_compare import compare


class EpochCompareTests(unittest.TestCase):
    def ledger(self, epoch, manifest="b", receipt="c"):
        return {
            "phase": "P1_ROSTER_SHARD_LEDGER", "trade_gate": "BLOCKED",
            "historical_PIT_verified": False, "full_market_bars_certified": False,
            "orders": [], "executable_candidates": [],
            "source_sha256": epoch * 64, "shard_count": 2,
            "completed": [{"index": 0, "issuer_count": 8, "manifest_sha256": manifest * 64,
                           "receipt_sha256": receipt * 64}],
            "completed_shards": 1, "completed_issuers": 8,
            "pending_shards": [1], "next_shard": 1, "failed_in_this_reconciliation": []
        }

    def test_equal_evidence_never_authorizes_reuse(self):
        result = compare(self.ledger("a"), self.ledger("d"))
        self.assertEqual(result["matching_manifest_and_receipt_shards"], 1)
        self.assertFalse(result["cross_epoch_reuse_authorized"])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_conflict_is_reported_not_merged(self):
        result = compare(self.ledger("a"), self.ledger("d", receipt="e"))
        self.assertEqual(result["conflicting_overlapping_shards"], [0])
        self.assertEqual(result["matching_manifest_and_receipt_shards"], 0)

    def test_unsafe_checkpoint_rejected(self):
        bad = self.ledger("d")
        bad["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            compare(self.ledger("a"), bad)


if __name__ == "__main__":
    unittest.main()
