"""Two authentic CNINFO SHA receipts, no hindsight release or tradable events."""
import copy
import json
from pathlib import Path
import unittest

from collector.p3_two_pdf_event_chain import KNOWN_DAYS, combine

ROOT = Path(__file__).resolve().parents[1] / "reports"


class RealIssuerPDFChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.early = json.loads((ROOT / "p3_cninfo_600421_early_20261021.json").read_text("utf-8"))
        cls.later = json.loads((ROOT / "p3_cninfo_600421_disclosure_pdf_20261021.json").read_text("utf-8"))

    def verify(self, early=None, later=None, day="2026-06-22"):
        return combine(copy.deepcopy(self.early) if early is None else early,
                       copy.deepcopy(self.later) if later is None else later,
                       day)

    def test_each_historical_date_fails_closed(self):
        for date in KNOWN_DAYS:
            with self.subTest(date=date):
                result = self.verify(day=date)
                self.assertEqual(result["status"], "TWO_ISSUER_DOCUMENT_SHA_RECEIPTS_PIT_BLOCKED")
                self.assertEqual(result["trade_gate"], "BLOCKED")
                self.assertEqual(result["orders"], [])
                self.assertEqual(result["candidate_universe"], [])
                self.assertEqual(result["executable_candidates"], [])
                self.assertIsNone(result["tradable_asof_day"])
                self.assertIsNone(result["historical_asof_document_availability"])

    def test_separate_restart_forecast_and_actual_unverified_date(self):
        r = self.verify()
        self.assertEqual([e["type"] for e in r["event_types"]], [
            "ISSUER_STATED_RESUMPTION_DATE",
            "ISSUER_FORECAST_FINAL_TRADING_DATE",
            "EXCHANGE_EFFECTIVE_DELIST_DATE_AUDIT_REFERENCE_ONLY",
        ])
        self.assertEqual(r["event_types"][0]["stated_date"], "2026-06-01")
        self.assertEqual(r["event_types"][1]["forecast"], "2026-06-22")
        self.assertEqual(r["event_types"][2]["reference_effective_date"], "2026-06-26")
        self.assertFalse(r["event_types"][2]["first_party_original_observed_in_runner"])
        self.assertIsNone(r["event_types"][2]["exchange_original_sha256"])

    def test_wrong_earlier_pdf_sha_refused(self):
        early = copy.deepcopy(self.early)
        early["source_observation"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA or URL mismatch"):
            self.verify(early=early)

    def test_wrong_later_pdf_sha_refused(self):
        later = copy.deepcopy(self.later)
        later["original_pdf_report"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "PDF hash changed"):
            self.verify(later=later)

    def test_claimed_historic_release_instant_refused(self):
        early = copy.deepcopy(self.early)
        early["source_observation"]["original_issuer_publication_instant_verified"] = True
        with self.assertRaisesRegex(ValueError, "official as-of state"):
            self.verify(early=early)

    def test_claimed_actual_resume_tradability_refused(self):
        early = copy.deepcopy(self.early)
        early["source_observation"]["tradability_on_resumption_date_exchange_verified"] = True
        with self.assertRaisesRegex(ValueError, "official as-of state"):
            self.verify(early=early)

    def test_change_earlier_expected_date_refused(self):
        early = copy.deepcopy(self.early)
        early["source_observation"]["issuer_stated_resumption_date"] = "2026-06-02"
        with self.assertRaisesRegex(ValueError, "chronology changed"):
            self.verify(early=early)

    def test_unfrozen_asof_day_refused(self):
        with self.assertRaisesRegex(ValueError, "Unsupported decision date"):
            self.verify(day="2026-05-25")


if __name__=="__main__":
    unittest.main()
