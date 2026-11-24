import copy
import unittest
from collector.p1_completion_guard import decision

EPOCH = "5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"


def fixture(done=400):
    from collector.p1_shard_ledger import reconcile
    plan = {
        "phase": "P1_FRESH_VENDOR_SHARD_PLAN", "source_sha256": EPOCH,
        "shard_count": 400,
        "shards": [{"index": i, "count": 8,
                    "sha256": f"{i + 100:064x}"} for i in range(400)],
    }
    entries = [{"index": i, "issuer_count": 8, "manifest_sha256": f"{i + 100:064x}",
                "receipt_sha256": f"{i + 1000:064x}"} for i in range(done)]
    ledger = {
        "phase": "P1_ROSTER_SHARD_LEDGER", "source_sha256": EPOCH, "shard_count": 400,
        "completed": entries, "completed_shards": done, "completed_issuers": done * 8,
        "pending_shards": list(range(done, 400)),
        "next_shard": done if done < 400 else None,
        "failed_in_this_reconciliation": [],
        "full_market_bars_certified": False, "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
    archive = {"source_sha256": EPOCH, "trade_gate": "BLOCKED",
               "archived_shards": list(range(done))}
    return ledger, archive, {"source_sha256": EPOCH}


class CompletionGuardTests(unittest.TestCase):
    def test_full_archived_400_is_noop_not_trade_unlock(self):
        ledger, archive, lock = fixture()
        report = decision(ledger, archive, lock)
        self.assertEqual(report["status"], "FULL_ARCHIVE_SKIP_VENDOR")
        self.assertFalse(report["should_collect"])
        self.assertFalse(report["historical_PIT_verified"])
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertEqual(report["orders"], [])

    def test_partial_allows_bounded_collector(self):
        ledger, archive, lock = fixture(393)
        self.assertTrue(decision(ledger, archive, lock)["should_collect"])
        self.assertEqual(decision(ledger, archive, lock)["pending_shards"],
                         list(range(393, 400)))

    def test_archive_mismatch_and_corruption_fail_closed(self):
        for case in ("missing", "duplicate", "extra", "epoch", "trade"):
            with self.subTest(case=case):
                ledger, archive, lock = fixture()
                if case == "missing":
                    archive["archived_shards"].pop()
                elif case == "duplicate":
                    archive["archived_shards"].append(399)
                elif case == "extra":
                    archive["archived_shards"][-1] = 400
                elif case == "epoch":
                    lock["source_sha256"] = "a" * 64
                else:
                    archive["trade_gate"] = "OPEN"
                with self.assertRaises(ValueError):
                    decision(ledger, archive, lock)

    def test_pending_inconsistent_fails_closed(self):
        ledger, archive, lock = fixture()
        ledger["pending_shards"] = [399]
        with self.assertRaises(ValueError):
            decision(ledger, archive, lock)

    def test_complete_guard_never_recaptures_on_manual_request(self):
        ledger, archive, lock = fixture()
        self.assertFalse(decision(ledger, archive, lock)["should_collect"])


if __name__ == "__main__":
    unittest.main()
