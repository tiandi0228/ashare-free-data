"""PIT acceptance must reject hindsight, forged official claims, and receipt drift."""
import copy
import unittest
from pathlib import Path

from collector.pit_acceptance_gate import audit_and_block, read_json

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "reports/p1_vendor_lifecycle_20261021.json"
BARS = ROOT / "reports/p1_pilot_16_source_digests_20261021.json"


class PITAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifecycle = read_json(LIFECYCLE)
        cls.bars = read_json(BARS)

    def evaluate(self, lifecycle=None, bars=None, day="2025-05-26"):
        return audit_and_block(
            lifecycle if lifecycle is not None else copy.deepcopy(self.lifecycle),
            bars if bars is not None else copy.deepcopy(self.bars),
            day,
        )

    def test_both_historical_decision_dates_remain_blocked(self):
        expected = {"2025-05-26": (3181, 32), "2026-10-20": (3195, 0)}
        for day, counts in expected.items():
            with self.subTest(day=day):
                result = self.evaluate(day=day)
                self.assertEqual(
                    (result["vendor_retrospective_candidate_count"],
                     result["vendor_later_delisted_count"]), counts)
                self.assertEqual(result["recovered_source_receipts"], 16)
                self.assertEqual(result["trade_gate"], "BLOCKED")
                self.assertEqual(result["candidate_universe"], [])
                self.assertEqual(result["orders"], [])
                self.assertFalse(result["trusted_historical_as_of_publication"])
                self.assertFalse(result["historical_ST_halt_delist_complete"])
                self.assertFalse(result["original_source_reverified_in_this_run"])
                self.assertFalse(result["p4_out_of_sample_certified"])

    def test_unknown_date_not_extrapolated(self):
        with self.assertRaisesRegex(ValueError, "No vendor snapshot"):
            self.evaluate(day="2024-10-21")

    def test_false_exchange_authentication_is_not_accepted(self):
        data = copy.deepcopy(self.lifecycle)
        data["source_report"]["source_exchange_authenticated"] = True
        with self.assertRaisesRegex(ValueError, "falsely marked"):
            self.evaluate(lifecycle=data)

    def test_receipt_digest_mismatch_detected(self):
        data = copy.deepcopy(self.lifecycle)
        data["source_original_csv_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "digest receipt"):
            self.evaluate(lifecycle=data)

    def test_missing_delisted_issuers_detected(self):
        data = copy.deepcopy(self.lifecycle)
        data["source_report"]["vendor_currently_delisted_mainboard_rows"] = 0
        with self.assertRaisesRegex(ValueError, "lifecycle receipt"):
            self.evaluate(lifecycle=data)

    def test_issuer_scope_drift_detected(self):
        data = copy.deepcopy(self.lifecycle)
        data["same_scope_membership_equality_verified"] = True
        with self.assertRaisesRegex(ValueError, "cannot certify"):
            self.evaluate(lifecycle=data)

    def test_original_sha_tamper_detected(self):
        bar = copy.deepcopy(self.bars)
        bar["audit_report"]["issuers"][0]["source_sha256"] = "not-a-digest"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.evaluate(bars=bar)

    def test_halt_count_tamper_detected(self):
        bar = copy.deepcopy(self.bars)
        bar["audit_report"]["issuers"][4]["suspended_status_rows"] = 0
        with self.assertRaisesRegex(ValueError, "accounting"):
            self.evaluate(bars=bar)

    def test_repeated_issuer_code_rejected(self):
        bar = copy.deepcopy(self.bars)
        bar["audit_report"]["issuers"][1]["code"] = bar["audit_report"]["issuers"][0]["code"]
        with self.assertRaisesRegex(ValueError, "identity"):
            self.evaluate(bars=bar)

    def test_false_full_market_backfill_rejected(self):
        bar = copy.deepcopy(self.bars)
        bar["audit_report"]["market_wide_backfill_complete"] = True
        with self.assertRaisesRegex(ValueError, "production-ready"):
            self.evaluate(bars=bar)


if __name__ == "__main__":
    unittest.main()
