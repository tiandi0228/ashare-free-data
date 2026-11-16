from datetime import date
import unittest
from unittest.mock import patch

from collector.p4_hs_2026_calendar_replay import FOLLOWUP, reconcile, reconcile_followup


class CalendarReplayTests(unittest.TestCase):
    def test_holidays_and_weekend_makeup_stay_closed(self):
        first, last = date(2026, 9, 25), date(2026, 10, 10)
        expected = {date(2026, 9, d) for d in (28, 29, 30)} | {date(2026, 10, d) for d in (8, 9)}
        r = reconcile({"sh": expected, "sz": expected | {last}}, first, last)
        self.assertTrue(r["published_holiday_ranges_agree"])
        self.assertEqual(r["venues"]["sh"]["expected"], 5)
        self.assertEqual(r["venues"]["sz"]["unexpected"], ["2026-10-10"])
        self.assertFalse(r["official_calendar_fully_verified"])

    def test_missing_session_is_venue_specific(self):
        session = date(2026, 2, 24)
        r = reconcile({"sh": {session}, "sz": set()}, session, session)
        self.assertEqual(r["venues"]["sh"]["missing"], [])
        self.assertEqual(r["venues"]["sz"]["missing"], ["2026-02-24"])

    def test_refuses_unverified_year(self):
        with self.assertRaisesRegex(ValueError, "2026"):
            reconcile({}, date(2027, 1, 1), date(2027, 1, 31))

    def test_followup_reopening_detects_missing_and_weekend_rows(self):
        sh = {date(2026, 9, 28), date(2026, 10, 8)}
        r = reconcile_followup({"sh": sh, "sz": {date(2026, 9, 28), date(2026, 10, 10)}})
        self.assertEqual(r["venues"]["sh"]["reopen_dates_missing"], [])
        self.assertEqual(r["venues"]["sz"]["reopen_dates_missing"], ["2026-10-08"])
        self.assertEqual(r["venues"]["sz"]["closed_dates_in_vendor_rows"], ["2026-10-10"])
        self.assertFalse(r["first_publication_clock_verified"])

    def test_followup_cannot_skip_expected_first_open(self):
        url, published, periods, weekends = FOLLOWUP["sh"]
        changed = (url, published, (periods[0], (*periods[1][:2], "2026-10-09")), weekends)
        with patch.dict(FOLLOWUP, {"sh": changed}), self.assertRaisesRegex(ValueError, "conflicts"):
            reconcile_followup({"sh": set(), "sz": set()})
