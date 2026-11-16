from datetime import date
import unittest

from collector.p4_hs_2026_calendar_replay import reconcile


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
