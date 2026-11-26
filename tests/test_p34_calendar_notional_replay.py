import unittest

from collector.p34_calendar_notional_replay import replay, session_status


class CalendarNotionalReplayTests(unittest.TestCase):
    def run_case(self, entry, exit, stop="9.80", market="SH", as_of="2026-09-24"):
        return replay(entry_day=entry, exit_day=exit, as_of=as_of, scenario={
            "synthetic_test_case": True, "market": market,
            "entry_actual_fill": "10.00", "stop_exit_actual_fill": stop, "shares": 400,
        })

    def test_holiday_tplus1_on_both_markets(self):
        for market in ("SH", "SZ"):
            for entry, exit in (("2026-09-24", "2026-09-28"), ("2026-09-30", "2026-10-08")):
                with self.subTest(market=market, entry=entry):
                    result = self.run_case(entry, exit, market=market)
                    self.assertEqual(result["scheduled_sessions_elapsed"], 1)
                    self.assertTrue(result["synthetic_checks_passed"])
                    self.assertFalse(result["fill_certified"])
                    self.assertEqual(result["orders"], [])
                    self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_closed_weekday_and_makeup_saturday(self):
        self.assertIn("ENTRY_OR_EXIT_SCHEDULED_CLOSED",
                      self.run_case("2026-09-24", "2026-09-25")["blocking_reasons"])
        self.assertEqual(session_status("SZ", "2026-10-10", "2026-09-24"), "SCHEDULED_CLOSED")

    def test_same_day_open_is_not_tplus1(self):
        self.assertIn("TPLUS1_NOT_MET",
                      self.run_case("2026-10-08", "2026-10-08")["blocking_reasons"])

    def test_outside_slice_and_before_notice_remain_unknown(self):
        for result in (
            self.run_case("2026-09-24", "2026-10-13"),
            self.run_case("2026-09-24", "2026-09-28", as_of="2026-09-17"),
        ):
            self.assertEqual(result["blocking_reasons"], ["CALENDAR_SCOPE_UNKNOWN"])
            self.assertIsNone(result["scheduled_sessions_elapsed"])

    def test_valid_calendar_does_not_override_position_budget(self):
        result = self.run_case("2026-09-30", "2026-10-08", stop="9.50")
        self.assertEqual(result["scheduled_sessions_elapsed"], 1)
        self.assertEqual(result["risk"]["modeled_net_stop_loss_yuan"], "211.98")
        self.assertEqual(result["risk"]["position_three_percent_risk_cap_yuan"], "120.00")
        self.assertEqual(result["blocking_reasons"], ["POSITION_NET_STOP_BUDGET_EXCEEDED"])

    def test_closure_and_risk_failures_both_survive(self):
        result = self.run_case("2026-09-24", "2026-09-25", stop="9.50")
        self.assertEqual(result["blocking_reasons"],
                         ["ENTRY_OR_EXIT_SCHEDULED_CLOSED", "POSITION_NET_STOP_BUDGET_EXCEEDED"])
