import unittest
from pathlib import Path
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
        self.assertTrue(report["vendor_shards_complete"])
        self.assertFalse(report["research_certified"])
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

    def archive_audit(self):
        # Same fields produced by p1_archive_audit.audit(..., replay=True).
        return {
            "source_sha256": "a" * 64,
            "trade_gate": "BLOCKED",
            "historical_PIT_verified": False,
            "archive_complete": True,
            "archive_csv_replay_enabled": True,
            "ledger_issuers": 8,
            "archived_issuers": 8,
            "archive_gap_issuers": 0,
            "independently_replayed_active_rows": 80,
            "independently_replayed_suspended_rows": 4,
        }

    def test_archive_audit_missing_or_incomplete_blocks_readiness(self):
        item = self.ledger()
        self.assertIn("CSV_ARCHIVE_AUDIT_UNAVAILABLE", assess(item)["unresolved_checks"])
        audit = self.archive_audit()
        self.assertNotIn("CSV_ARCHIVE_NOT_CERTIFIED", assess(item, audit)["unresolved_checks"])
        audit["archived_issuers"] = 7
        self.assertIn("CSV_ARCHIVE_NOT_CERTIFIED", assess(item, audit)["unresolved_checks"])

    def test_archive_readiness_requires_independent_byte_replay(self):
        item = self.ledger()
        original = self.archive_audit()
        failures = [
            {"archive_csv_replay_enabled": False},
            {"archive_csv_replay_enabled": None},
            {"historical_PIT_verified": True},
            {"historical_PIT_verified": None},
            {"ledger_issuers": 7},
            {"ledger_issuers": True},
            {"archive_gap_issuers": False},
            {"independently_replayed_active_rows": None},
            {"independently_replayed_active_rows": -1},
            {"independently_replayed_suspended_rows": -1},
            {"independently_replayed_active_rows": 0,
             "independently_replayed_suspended_rows": 0},
        ]
        for changes in failures:
            with self.subTest(changes=changes):
                audit = dict(original, **changes)
                result = assess(item, audit)
                self.assertIn("CSV_ARCHIVE_NOT_CERTIFIED", result["unresolved_checks"])
                self.assertFalse(result["research_certified"])
                self.assertFalse(result["buy_recommendations_authorized"])
                self.assertEqual(result["trade_gate"], "BLOCKED")

        missing = self.archive_audit()
        del missing["archive_csv_replay_enabled"]
        self.assertIn("CSV_ARCHIVE_NOT_CERTIFIED",
                      assess(item, missing)["unresolved_checks"])

    def test_archive_audit_from_different_epoch_is_rejected(self):
        item=self.ledger()
        audit={"source_sha256":"b"*64,"trade_gate":"BLOCKED","archive_complete":True,
               "archived_issuers":8,"archive_gap_issuers":0}
        report=assess(item,audit)
        self.assertIn("CSV_ARCHIVE_NOT_CERTIFIED",report["unresolved_checks"])
        self.assertFalse(report["buy_recommendations_authorized"])

    def test_readiness_code_changes_use_offline_ci_not_live_vendor_collection(self):
        root = Path(__file__).resolve().parents[1]
        live = (root / ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        offline = (root / ".github/workflows/p1-readiness-contract-ci.yml").read_text()
        live_push = live.split("  schedule:", 1)[0]
        # Pure readiness gate edits must not consume real Baostock requests,
        # produce cloud CSVs, or fan out into P3/P4 workflow_run jobs.
        self.assertNotIn("      - 'collector/p1_research_readiness.py'", live_push)
        self.assertNotIn("      - 'tests/test_p1_research_readiness.py'", live_push)
        # Keep scheduled and explicit manual collection available.
        self.assertIn("  schedule:", live)
        self.assertIn("  workflow_dispatch:", live)
        # Offline pull-request CI must cover the affected code and the
        # source workflow itself, so trigger regressions remain testable.
        self.assertIn("  pull_request:", offline)
        self.assertIn("      - 'collector/p1_research_readiness.py'", offline)
        self.assertIn("      - 'tests/test_p1_research_readiness.py'", offline)
        self.assertIn("      - '.github/workflows/p1-fresh-vendor-roster.yml'", offline)

    def test_tampered_open_gate_rejected(self):
        item = self.ledger()
        item["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            assess(item)


if __name__ == "__main__":
    unittest.main()
