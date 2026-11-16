from collections import Counter
from datetime import date
import unittest
from unittest.mock import patch

from collector.p4_hs_2026_calendar_replay import FOLLOWUP, reconcile, reconcile_early_notices, reconcile_followup, record_row, reopen_activity


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

    def test_early_checks_only_apply_to_windows_covering_entire_holiday(self):
        reopen = date(2026, 1, 5)
        observed = {"sh": {reopen}, "sz": {reopen}}
        self.assertEqual(reconcile_early_notices(observed, date(2026, 1, 2), reopen), {})
        results = reconcile_early_notices(observed, date(2026, 1, 1), reopen)
        self.assertEqual(list(results), ["new_year"])
        self.assertEqual(results["new_year"]["venues"]["sh"]["notice_kind"], "ANNUAL")
        self.assertEqual(results["new_year"]["venues"]["sz"]["reopen_dates_observed"], ["2026-01-05"])

    def test_suspended_or_zero_turnover_rows_do_not_prove_activity(self):
        day = "2026-01-05"
        observed = {"sh": set(), "sz": set()}
        activity = {"sh": Counter(), "sz": Counter()}
        for status, volume, amount in (("0", "", ""), ("1", "10", "0"), ("1", "10", "99")):
            record_row(observed, activity, dict(code="sh.600001", date=day, tradestatus=status,
                                                volume=volume, amount=amount))
        record_row(observed, activity, dict(code="sz.000001", date=day, tradestatus="0",
                                            volume="", amount=""))
        self.assertIn(date.fromisoformat(day), observed["sz"])
        r = reopen_activity(activity, [day])
        self.assertEqual(r["sh"][day]["active_positive_volume_and_amount_rows"], 1)
        self.assertEqual(r["sz"][day]["status"], "NO_VENDOR_TRADING_ACTIVITY_OBSERVED")
