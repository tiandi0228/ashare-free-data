"""Conservative issuer-claimed halt window is never trade authorization."""
import copy
import unittest
from collector.p3_600150_dated_media_crosscheck import build
from collector.p3_600150_halt_window_exclusion import overlay, may_execute_on_day


class HaltWindowTests(unittest.TestCase):
    def test_four_weekday_exclusion_dates(self):
        result = overlay()
        self.assertEqual(result["research_weekday_exclusion_dates"], [
            "2025-08-13", "2025-08-14", "2025-08-15", "2025-08-18"])
        self.assertEqual(result["issuer_claimed_resume_day"], "2025-08-19")

    def test_outside_halt_unknown_not_tradable(self):
        result = overlay()
        self.assertEqual(result["outside_window_status"], "UNKNOWN_NOT_CERTIFIED_TRADABLE")
        for day in ("2025-08-12", "2025-08-13", "2025-08-18", "2025-08-19", "2026-11-12"):
            self.assertIs(may_execute_on_day(result, day), False)

    def test_blocks_only_not_certifies(self):
        result = overlay()
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["executable_candidates"], [])
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["fills_verified"], 0)

    def test_reject_promoted_source(self):
        source = build()
        source["rows"][0]["exchange_effective_interval_authenticated"] = True
        with self.assertRaises(ValueError): overlay(source)

    def test_reject_changed_halt_start(self):
        source = build()
        source["rows"][0]["effective_date_claim_from_issuer_notice"] = "2025-08-12"
        with self.assertRaises(ValueError): overlay(source)

    def test_reject_missing_and_duplicate_resume(self):
        source = build()
        source["rows"] = [source["rows"][0]]
        with self.assertRaises(ValueError): overlay(source)
        source["rows"].append(copy.deepcopy(source["rows"][0]))
        with self.assertRaises(ValueError): overlay(source)

    def test_reject_forged_truthy_flags(self):
        source = build()
        source["rows"][0]["candidate_asof_trade_eligible"] = 1
        with self.assertRaises(ValueError): overlay(source)

    def test_reject_open_gate(self):
        source = build()
        source["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError): overlay(source)

    def test_reject_invalid_day(self):
        with self.assertRaises(ValueError): may_execute_on_day(overlay(), "2025-02-30")

    def test_reject_forged_overlay(self):
        result = overlay()
        result["historical_PIT_verified"] = True
        with self.assertRaises(ValueError): may_execute_on_day(result, "2025-08-19")
