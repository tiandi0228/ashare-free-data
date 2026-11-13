import unittest
from collections import Counter

from collector.p3_calendar_source_replay import FILE, SHA, ledger, lookup


class CalendarSourceReplayTests(unittest.TestCase):
    def setUp(self):
        self.raw = FILE.read_bytes()

    def test_pinned_official_bytes_replay_all_scoped_days(self):
        report = ledger(self.raw, "2026-09-24")
        self.assertEqual(Counter(r["status"] for r in report["rows"]), {
            "NOTICE_HOLIDAY_CLOSED": 10, "NOTICE_EXPLICIT_REOPEN": 2,
            "INFERRED_WEEKEND_CLOSED": 2, "INFERRED_WEEKDAY_OPEN": 5,
        })
        self.assertTrue(all(r["source_sha256"] == SHA for r in report["rows"]))
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertFalse(report["full_historical_calendar_authenticated"])

    def test_announcement_date_has_no_intraday_attestation(self):
        for date in ("2026-09-16", "2026-09-17"):
            report = ledger(self.raw, date)
            self.assertEqual(lookup(report, "SZ", "2026-09-25"), "UNKNOWN_AS_OF")
            self.assertIsNone(report["rows"][0]["source_sha256"])
        report = ledger(self.raw, "2026-09-18")
        self.assertEqual(lookup(report, "SZ", "2026-09-28"), "NOTICE_EXPLICIT_REOPEN")
        self.assertFalse(report["first_publication_timestamp_authenticated"])

    def test_no_cross_market_or_outside_slice_inference(self):
        report = ledger(self.raw, "2026-09-24")
        self.assertEqual(lookup(report, "SH", "2026-09-25"), "UNKNOWN")
        self.assertEqual(lookup(report, "SZ", "2026-10-13"), "UNKNOWN")
        self.assertEqual(lookup(report, "SZ", "2026-10-08"), "NOTICE_EXPLICIT_REOPEN")

    def test_tampered_or_missing_original_is_rejected(self):
        for raw in (b"", self.raw + b" "):
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                ledger(raw, "2026-09-24")
