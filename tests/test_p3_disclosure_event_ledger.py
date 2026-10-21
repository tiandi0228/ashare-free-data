"""Test actual SHA-only receipt, forecast effective-date and hindsight quarantine."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from collector.p3_disclosure_event_ledger import DATES, normalize_notice, ISSUER

REPORT = Path(__file__).resolve().parents[1] / "reports/p3_cninfo_600421_disclosure_pdf_20261021.json"


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads(REPORT.read_text("utf-8"))

    def run_gate(self, info=None, day="2026-06-22"):
        return normalize_notice(copy.deepcopy(self.receipt) if info is None else info, day)

    def test_five_decision_dates_never_release_issuer(self):
        for day in DATES:
            with self.subTest(day=day):
                r = self.run_gate(day=day)
                self.assertEqual(r["issuer"], ISSUER)
                self.assertEqual(r["trade_gate"], "BLOCKED")
                self.assertEqual(r["candidate_universe"], [])
                self.assertEqual(r["executable_candidates"], [])
                self.assertEqual(r["orders"], [])
                self.assertIsNone(r["issuer_tradable_as_of_day"])
                self.assertIsNone(r["content_could_have_been_observed_as_of_day"])
                self.assertFalse(r["known_historical_asof"])

    def test_predicted_last_trading_day_never_becomes_effective_date(self):
        r = self.run_gate(day="2026-06-26")
        forecast, exchange = r["non_executable_research_events"]
        self.assertEqual(forecast["kind"], "ISSUER_EXPECTED_FINAL_TRADING_DATE")
        self.assertEqual(forecast["forecast_date"], "2026-06-22")
        self.assertFalse(forecast["is_actual_delisting_effective_date"])
        self.assertEqual(exchange["claimed_effective_date_for_independent_audit"], "2026-06-26")
        self.assertIsNone(exchange["original_exchange_document_sha256"])
        self.assertFalse(exchange["accepted_as_verified_trading_state"])

    def test_no_historical_publication_time_inferred_from_url(self):
        r = self.run_gate(day="2026-06-20")
        self.assertEqual(r["issuer_notice_url_calendar_date"], "2026-06-19")
        self.assertFalse(r["issuer_notice_actual_release_instant_verified"])
        self.assertIsNone(r["content_could_have_been_observed_as_of_day"])

    def test_unverified_previous_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "Decision day not covered"):
            self.run_gate(day="2026-06-01")

    def test_sha_changes_fail_closed(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["original_pdf_report"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "PDF hash changed"):
            self.run_gate(receipt)

    def test_fake_sse_sha_evidence_fails_closed(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["sse_original_sha_not_obtained"] = False
        with self.assertRaisesRegex(ValueError, "Unverified SSE follow-up"):
            self.run_gate(receipt)

    def test_forged_release_instant_does_not_unlock(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["original_pdf_report"]["historical_asof_publication_timestamp_verified"] = True
        with self.assertRaisesRegex(ValueError, "falsely elevated"):
            self.run_gate(receipt)

    def test_forged_actual_delist_from_risk_notice_fails(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["original_pdf_report"]["actual_exchange_delist_effective_date_verified_from_this_pdf"] = True
        with self.assertRaisesRegex(ValueError, "falsely elevated"):
            self.run_gate(receipt)

    def test_wrong_run_id_does_not_reuse_other_data(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["acquisition_run_id"] = 39578232761
        with self.assertRaisesRegex(ValueError, "Unexpected cloud acquisition identity"):
            self.run_gate(receipt)

    def test_sources_without_raw_bytes_are_not_replayable(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["original_pdf_bytes_stored_in_public_repo"] = True
        with self.assertRaisesRegex(ValueError, "retention scope changed"):
            self.run_gate(receipt)


if __name__ == "__main__":
    unittest.main()
