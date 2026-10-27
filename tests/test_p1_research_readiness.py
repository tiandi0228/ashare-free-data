import unittest
from collector.p1_research_readiness import assess, assess_or_block, unavailable


class ReadinessTests(unittest.TestCase):
    def ledger(self):
        return {
            "phase": "P1_ROSTER_SHARD_LEDGER",
            "source_sha256": "a" * 64, "shard_count": 2,
            "completed": [{"index": 0, "issuer_count": 8, "manifest_sha256": "b" * 64, "receipt_sha256": "c" * 64}],
            "completed_shards": 1, "completed_issuers": 8,
            "pending_shards": [1], "next_shard": 1,
            "failed_in_this_reconciliation": [],
            "full_market_bars_certified": False,
            "historical_PIT_verified": False,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []
        }

    def test_missing_ledger_produces_explicit_blocked_report(self):
        report = unavailable()
        self.assertEqual(report["unresolved_checks"], ["CURRENT_LEDGER_UNAVAILABLE"])
        self.assertFalse(report["research_data_complete"])
        self.assertFalse(report["buy_recommendations_authorized"])
        self.assertEqual(report["trade_gate"], "BLOCKED")

    def test_malformed_ledger_is_reported_blocked(self):
        bad = self.ledger()
        bad["completed_shards"] = 2
        report = assess_or_block(bad)
        self.assertEqual(report["unresolved_checks"], ["CURRENT_LEDGER_INVALID"])
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertFalse(report["buy_recommendations_authorized"])

    def test_non_mapping_ledger_is_reported_blocked(self):
        report = assess_or_block([])
        self.assertEqual(report["unresolved_checks"], ["CURRENT_LEDGER_INVALID"])

    def test_partial_ledger_not_actionable(self):
        report = assess(self.ledger())
        self.assertFalse(report["buy_recommendations_authorized"])
        self.assertIn("HISTORICAL_VENDOR_SHARDS_INCOMPLETE", report["unresolved_checks"])

    def test_all_vendor_shards_still_not_certified(self):
        item = self.ledger()
        item["completed"].append({"index": 1, "issuer_count": 8, "manifest_sha256": "d" * 64, "receipt_sha256": "e" * 64})
        item.update(completed_shards=2, completed_issuers=16, pending_shards=[], next_shard=None)
        report = assess(item)
        self.assertTrue(report["research_data_complete"])
        self.assertFalse(report["buy_recommendations_authorized"])
        self.assertIn("HISTORICAL_PIT_NOT_AUTHENTICATED", report["unresolved_checks"])

    def test_full_vendor_coverage_never_implies_realtime_execution_ready(self):
        item = self.ledger()
        item["completed"].append({"index": 1, "issuer_count": 8,
                                  "manifest_sha256": "d" * 64, "receipt_sha256": "e" * 64})
        item.update(completed_shards=2, completed_issuers=16,
                    pending_shards=[], next_shard=None)
        report = assess(item)
        self.assertFalse(report["realtime_execution_checks_verified"])
        self.assertIn("REALTIME_QUOTE_FRESHNESS_NOT_VERIFIED", report["unresolved_checks"])
        self.assertIn("COMPLETE_ONE_MINUTE_BAR_NOT_VERIFIED", report["unresolved_checks"])
        self.assertFalse(report["buy_recommendations_authorized"])

    def test_archive_audit_missing_or_incomplete_blocks_readiness(self):
        item=self.ledger()
        self.assertIn("CSV_ARCHIVE_AUDIT_UNAVAILABLE",assess(item)["unresolved_checks"])
        audit={"trade_gate":"BLOCKED","archive_complete":True,
               "archived_issuers":8,"archive_gap_issuers":0}
        self.assertNotIn("CSV_ARCHIVE_NOT_CERTIFIED",assess(item,audit)["unresolved_checks"])
        audit["archived_issuers"]=7
        self.assertIn("CSV_ARCHIVE_NOT_CERTIFIED",assess(item,audit)["unresolved_checks"])

    def test_tampered_open_gate_rejected(self):
        item = self.ledger()
        item["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            assess(item)


if __name__ == "__main__":
    unittest.main()
