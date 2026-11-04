"""An as-of Friday preflight may not use future vendor prices or certify orders."""
import copy
import unittest

from collector.p4_friday_asof_preentry_guard import (
    CATEGORIES, audit, calendar_diagnostic, classify_signal_day, signal_date,
)


def fixture():
    return {
        "phase":"P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES",
        "status":"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
        "archive_commit_sha":"a"*40,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "strategy_backtest_certified":False,
        "fills_assumed":0,"trades_assumed":0,
        "observed_next_open_to_third_close":5,
        "observed_price_pairs":[{
            "issuer":f"sh.60000{i}",
            "signal_known_after_close_date":day,
            "next_vendor_date":"2026-12-31",
            "next_vendor_open":"10",
            "third_vendor_close":"11",
            "next_open_fill_assumed":False,
            "exit_close_fill_assumed":False,
            "T_plus_1_execution_verified":False,
            "trade_return":None,
        } for i,day in enumerate((
            "2026-11-02", "2026-11-03", "2026-11-04",
            "2026-11-05", "2026-11-06"))
        ]
    }


class AsOfFridayPreentryTests(unittest.TestCase):
    def test_research_weekdays_do_not_issue_buy(self):
        r=audit(fixture())
        self.assertEqual(r["status"],
                         "ASOF_WEEKDAY_ONLY_NO_AUTHENTICATED_CALENDAR_NO_TRADES")
        self.assertEqual(r["verified_mature_proxy_signals"],5)
        self.assertEqual(r["conditional_next_weekday_screen"],{
            CATEGORIES[0]:2, CATEGORIES[1]:2, CATEGORIES[2]:1,
        })
        self.assertEqual(r["calendar_certificate_missing_for_all"],5)
        self.assertEqual(r["approved_entries"],0)
        self.assertEqual(r["first_publication_of_exchange_calendar_verified"],0)
        self.assertFalse(r["future_vendor_bars_used_in_entry_precheck"])
        self.assertFalse(r["historical_calendar_asof_authenticated"])
        self.assertFalse(r["preentry_executable_signal_generated"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["actionable_buy_signals"],[])

    def test_future_vendor_prices_dates_and_outcomes_cannot_change_weekday_counts(self):
        a=fixture()
        b=copy.deepcopy(a)
        for row in b["observed_price_pairs"]:
            row.update(next_vendor_date="2030-01-01",
                       next_vendor_open="9999999",
                       third_vendor_close="-999",
                       observed_overnight_gap_pct="inf",
                       later_weekday_from_vendor_rows="FRIDAY",
                       future_vendor_status=["HALT","CLOSED"],
                       profit_after_third_vendor_date="900%")
        x,y=audit(a),audit(b)
        self.assertEqual(x["status"],y["status"])
        self.assertEqual(x["signal_weekday_histogram"],y["signal_weekday_histogram"])
        self.assertEqual(x["conditional_next_weekday_screen"],
                         y["conditional_next_weekday_screen"])
        self.assertEqual(x["calendar_certificate_missing_for_all"],
                         y["calendar_certificate_missing_for_all"])
        self.assertEqual(y["approved_entries"],0)

    def test_calendar_research_never_authenticates_itself(self):
        sessions=["2026-11-02","2026-11-03","2026-11-04",
                  "2026-11-05","2026-11-06"]
        monday=calendar_diagnostic("2026-11-02",sessions)
        self.assertEqual(monday["status"],
                "RESEARCH_DATE_ARITHMETIC_COMPATIBLE_UNAUTHENTICATED")
        self.assertEqual(monday["hypothetical_next_session"],"2026-11-03")
        self.assertEqual(monday[
            "calendar_sessions_after_hypothetical_entry_before_weekend"],3)
        wednesday=calendar_diagnostic("2026-11-04",sessions)
        self.assertEqual(wednesday["status"],
                "RESEARCH_VETO_EARLY_WEEKEND_BEFORE_3_SESSIONS")
        self.assertEqual(wednesday[
            "calendar_sessions_after_hypothetical_entry_before_weekend"],1)
        thursday=calendar_diagnostic("2026-11-05",sessions)
        self.assertEqual(thursday["status"],"RESEARCH_VETO_FRIDAY_ENTRY_TPLUS1")
        self.assertEqual(thursday["hypothetical_next_session"],"2026-11-06")
        for report in (monday,wednesday,thursday):
            self.assertFalse(report["calendar_asof_authenticity_certified"])
            self.assertFalse(report["trade_authorized"])
            self.assertFalse(report["historical_issuer_pit_certified"])
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertEqual(report["orders"],[])

    def test_friday_signal_prospective_monday_entry_calendar_arithmetic(self):
        sessions=[
            "2026-11-06","2026-11-09","2026-11-10",
            "2026-11-11","2026-11-12","2026-11-13",
        ]
        r=calendar_diagnostic("2026-11-06",sessions)
        self.assertEqual(r["status"],
                "RESEARCH_DATE_ARITHMETIC_COMPATIBLE_UNAUTHENTICATED")
        self.assertEqual(r[
            "calendar_sessions_after_hypothetical_entry_before_weekend"],4)
        self.assertFalse(r["trade_authorized"])

    def test_holiday_calendar_changes_friday_weekday_assumptions(self):
        # Hypothetical Friday exchange closure shifts the last potential
        # liquidation session to Thursday and cannot be inferred by weekday.
        r=calendar_diagnostic("2026-11-02",[
            "2026-11-02","2026-11-03","2026-11-04","2026-11-05"])
        self.assertEqual(r["status"],
                         "RESEARCH_VETO_EARLY_WEEKEND_BEFORE_3_SESSIONS")
        self.assertEqual(r["hypothetical_week_end_exit_session"],"2026-11-05")
        self.assertFalse(r["trade_authorized"])

    def test_missing_or_invalid_calendar_fail_closed(self):
        for calendar,expected in [
            (None,"BLOCK_MISSING_PREPUBLISHED_EXCHANGE_CALENDAR"),
            ([],"BLOCK_MALFORMED_CALENDAR_RESEARCH_INPUT"),
            (["2026-11-02","2026-11-02"],
             "BLOCK_DUPLICATED_OR_UNSORTED_CALENDAR"),
            (["2026-11-03","2026-11-04"],
             "BLOCK_SIGNAL_DAY_ABSENT_FROM_CALENDAR"),
            (["2026-11-02","2026-11-01"],
             "BLOCK_MALFORMED_CALENDAR_RESEARCH_INPUT"),
            (["2026-11-02","2026-12-01"],
             "BLOCK_CALENDAR_GAP_LONGER_THAN_14_DAYS"),
        ]:
            with self.subTest(calendar=calendar):
                r=calendar_diagnostic("2026-11-02",calendar)
                self.assertEqual(r["status"],expected)
                self.assertFalse(r["trade_authorized"])
                self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_unsafe_source_and_invalid_signal_rejected(self):
        cases = [
            lambda x:x.update(trade_gate="OPEN"),
            lambda x:x.update(historical_PIT_verified=True),
            lambda x:x.update(strategy_backtest_certified=True),
            lambda x:x["orders"].append({"side":"BUY"}),
            lambda x:x["observed_price_pairs"][0].update(
                next_open_fill_assumed=True),
            lambda x:x["observed_price_pairs"][0].update(
                trade_return="5"),
            lambda x:x["observed_price_pairs"][0].update(
                signal_known_after_close_date="2026-11-07"),
            lambda x:x["observed_price_pairs"][0].update(
                signal_known_after_close_date="2026-11-02T15:00:00"),
            lambda x:x["observed_price_pairs"][0].update(issuer="sz.300001"),
            lambda x:x["observed_price_pairs"][1].update(
                issuer="sh.600000",
                signal_known_after_close_date="2026-11-02"),
            lambda x:x.update(observed_next_open_to_third_close=4),
            lambda x:x.update(archive_commit_sha="BAD"),
        ]
        for change in cases:
            with self.subTest(change=change):
                src=fixture()
                change(src)
                r=audit(src)
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["trade_gate"],"BLOCKED")
                self.assertEqual(r["approved_entries"],0)
                self.assertEqual(r["orders"],[])


if __name__=="__main__":
    unittest.main()
