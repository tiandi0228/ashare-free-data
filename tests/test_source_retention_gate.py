"""Real GitHub inventory tests plus tampering and retention expiration."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import unittest

from collector.source_retention_gate import audit, parse_utc

ROOT = Path(__file__).resolve().parents[1] / "reports"


class SourceRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = [
            json.loads((ROOT / n).read_text(encoding="utf-8"))
            for n in (
                "source_artifact_inventory_20261021.json",
                "p1_pilot_16_source_digests_20261021.json",
                "p1_delisted_8_source_digests_20261021.json",
                "p3_two_issuer_vendor_st_replay_20261021.json",
            )
        ]

    def check(self, change=None):
        source = copy.deepcopy(self.reports)
        if change:
            change(source)
        return audit(*source)

    def test_verified_four_artifacts_still_not_permanent_archive(self):
        report = self.check()
        self.assertEqual(report["original_artifacts_expected"], 4)
        self.assertEqual(report["original_artifacts_currently_available"], 4)
        self.assertEqual(report["status"], "TEMPORARY_ORIGINALS_PRESENT_PERMANENT_REPLAY_BLOCKED")
        self.assertLessEqual(report["minimum_remaining_days"], 14)
        self.assertEqual(len(report["source_artifacts"]), 4)
        self.assertTrue(all(x["state"] == "AVAILABLE_EXPIRING"
                            for x in report["source_artifacts"]))
        self.assertFalse(report["retention_is_permanent"])
        self.assertFalse(report["license_for_public_vendor_CSV_redistribution_verified"])
        self.assertFalse(report["public_GitHub_Releases_is_approved_storage"])
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertEqual(report["orders"], [])
        self.assertEqual(report["candidate_universe"], [])

    def test_missing_original_does_not_count_as_available(self):
        def change(x):
            x[0]["runs"][0]["artifacts"] = []
        report = self.check(change)
        self.assertEqual(report["original_artifacts_currently_available"], 3)
        self.assertEqual(report["status"], "ORIGINAL_SOURCE_REPLAY_MISSING_OR_EXPIRED")
        self.assertEqual(report["source_artifacts"][0]["state"], "MISSING")
        self.assertFalse(report["original_source_archive_replay_ready"])

    def test_expired_time_is_not_available_even_if_api_says_not_expired(self):
        def change(x):
            x[0]["inspected_at_utc"] = "2026-11-05T12:00:00Z"
        report = self.check(change)
        self.assertEqual(report["original_artifacts_currently_available"], 0)
        self.assertTrue(all(a["state"] == "EXPIRED"
                            for a in report["source_artifacts"]))

    def test_forged_missing_expired_boolean_rejected(self):
        def change(x):
            del x[0]["runs"][0]["artifacts"][0]["expired"]
        with self.assertRaisesRegex(ValueError, "expired state"):
            self.check(change)

    def test_repeated_artifact_run_rejected(self):
        def change(x):
            x[0]["runs"][1]["run_id"] = x[0]["runs"][0]["run_id"]
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.check(change)

    def test_impossibly_long_public_retention_rejected(self):
        def change(x):
            v = x[0]["runs"][0]["artifacts"][0]
            v["expires_at"] = "2027-10-21T08:54:59Z"
        with self.assertRaisesRegex(ValueError, "Impossible public"):
            self.check(change)

    def test_wrong_source_sha_receipt_identity_rejected(self):
        def change(x):
            x[2]["original_data_artifact_id"] = 0
        with self.assertRaisesRegex(ValueError, "eight-source"):
            self.check(change)

    def test_artifact_retention_never_authenticates_exchange_or_oos(self):
        report = self.check()
        self.assertFalse(report["historical_point_in_time_authority_verified"])
        self.assertFalse(report["fully_replayable_full_market_verified"])
        self.assertFalse(report["p4_oos_ready"])
        self.assertTrue(any("cninfo" in x for x in
                            report["source_originals_unavailable_even_before_expiration"]))
        self.assertEqual(report["trade_gate"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
