"""Strict P4 issuer/session evidence contract and fail-closed regression."""
import unittest

from collector.p4_issuer_session_gate import check
from collector.p4_unified_execution_preflight import assess as unified

BASE = {
    "issuer": "sh.600150", "session_day": "2026-10-26",
    "official_calendar_sessions": ["2026-10-23", "2026-10-26"],
    "issuer_status": "TRADING", "official_status_authenticated": True,
    "official_calendar_authenticated": True,
    "market_orderbook_evidence": True,
}


class P4StrictInputTests(unittest.TestCase):
    def test_valid_main_board_never_certifies_fill(self):
        for issuer in ("sh.600150", "sh.601006", "sh.603000",
                       "sh.605100", "sz.000089", "sz.001288",
                       "sz.002249", "sz.003001"):
            with self.subTest(issuer=issuer):
                result = check(**{**BASE, "issuer": issuer})
                self.assertEqual(result["outcome"], "SOURCE_EVIDENCE_NEEDS_INDEPENDENT_FILL_REPLAY")
                self.assertFalse(result["fill_verified"])
                self.assertEqual(result["trade_gate"], "BLOCKED")
                self.assertEqual(result["orders"], [])

    def test_ineligible_or_malformed_issuer_is_rejected(self):
        for issuer in ("sh.688001", "sh.689001", "sz.300015",
                       "sz.301015", "bj.920001", "sh.600150extra",
                       "sh.x", "sz.", "600150", "", None, 600150):
            with self.subTest(issuer=issuer), self.assertRaises(ValueError):
                check(**{**BASE, "issuer": issuer})

    def test_authentication_flags_must_be_actual_booleans(self):
        for key in ("official_status_authenticated",
                    "official_calendar_authenticated", "market_orderbook_evidence"):
            for value in (1, 0, "true", "false", None, [], {}):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    check(**{**BASE, key: value})

    def test_noncanonical_invalid_or_weekend_session_rejected(self):
        for raw in ("20261026", "2026-1-02", "2026-10-25",
                    "2026-02-30", "2026-10-26T09:30", "", None, 20261026):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                check(**{**BASE, "session_day": raw})

    def test_calendar_invalid_or_out_of_order_rejected(self):
        for days in (
            ["2026-10-26", "2026-10-23"],
            ["2026-10-23", "2026-10-23", "2026-10-26"],
            ["2026-10-23", "2026-10-25", "2026-10-26"],
            ["2026-10-23", "20261026"],
            ["2026-10-23", None],
            "2026-10-26", None,
        ):
            with self.subTest(days=days), self.assertRaises(ValueError):
                check(**{**BASE, "official_calendar_sessions": days})

    def test_missing_day_stays_blocked_without_inventing_session(self):
        result = check(**{**BASE, "official_calendar_sessions": ["2026-10-23"]})
        self.assertEqual(result["outcome"], "MARKET_CLOSED_OR_SESSION_NOT_PROVEN")
        self.assertFalse(result["fill_verified"])

    def test_suspended_or_unverified_stays_blocked(self):
        for case, expected in (
            ({"issuer_status": "SUSPENDED"}, "ISSUER_SUSPENDED_NO_EXECUTION"),
            ({"issuer_status": "UNKNOWN"}, "ISSUER_STATUS_UNKNOWN_BLOCKED"),
            ({"official_status_authenticated": False}, "ISSUER_STATUS_UNAUTHENTICATED"),
            ({"official_calendar_authenticated": False}, "OFFICIAL_SESSION_CALENDAR_UNAUTHENTICATED"),
            ({"market_orderbook_evidence": False}, "TRADING_STATUS_NOT_FILL_EVIDENCE"),
        ):
            with self.subTest(case=case):
                result = check(**{**BASE, **case})
                self.assertEqual(result["outcome"], expected)
                self.assertFalse(result["fill_verified"])

    def test_unified_preflight_rejects_issuer_shape_before_execution(self):
        from tests.test_p4_unified_execution_preflight import BASE as unified_base
        with self.assertRaises(ValueError):
            unified(**{**unified_base, "issuer": "sz.300015"})
        with self.assertRaises(ValueError):
            unified(**{**unified_base, "official_calendar_authenticated": 1})
        accepted = unified(**unified_base)
        self.assertTrue(accepted["candidate_for_independent_receipt_replay"])
        self.assertFalse(accepted["fill_certified"])
        self.assertEqual(accepted["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
