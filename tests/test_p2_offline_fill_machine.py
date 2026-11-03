"""Offline-only fills: no broker I/O, same-day sell or implied intrabar order."""
import copy
import unittest
from collector.p2_offline_fill_machine import simulation

DAYS=["2026-11-02","2026-11-03","2026-11-04",
      "2026-11-05","2026-11-06","2026-11-09"]
def buy_scenario(events=None):
    if events is None:
        events=[
            {"date":DAYS[0],"type":"BUY_SUBMIT","shares":200,"limit":"10.00"},
            {"date":DAYS[0],"type":"BUY_FILL","shares":100,"price":"9.99"},
            {"date":DAYS[0],"type":"BUY_FILL","shares":100,"price":"9.98"},
            {"date":DAYS[3],"type":"EXIT_TRIGGER","reason":"TIME_EXIT",
             "same_bar_both_touched":False},
            {"date":DAYS[3],"type":"SELL_SUBMIT","shares":200,"limit":"10.30"},
            {"date":DAYS[3],"type":"SELL_FILL","shares":80,"price":"10.30"},
            {"date":DAYS[3],"type":"SELL_FILL","shares":120,"price":"10.35"},
        ]
    return {"code":"002249","is_st":False,"halted":False,
            "initial_cash_cny":"8000","trading_dates":DAYS,
            "events":events}

class OfflineFillTests(unittest.TestCase):
    def test_partial_buy_sell_and_three_trading_day_exit(self):
        x=simulation(buy_scenario())
        self.assertEqual(x["status"],"OFFLINE_SCENARIO_REPLAYED_NOT_EXECUTABLE")
        self.assertEqual(x["remaining_shares"],0)
        self.assertIsNone(x["open_simulated_order"])
        self.assertTrue(x["exit_intent_observed"])
        self.assertEqual(x["simulation_events"][-1]["shares"],120)
        self.assertEqual(x["orders"],[])
        self.assertEqual(x["trade_gate"],"BLOCKED")
        self.assertFalse(x["simulated_fill_verified"])

    def test_same_day_sell_fails_t_plus_one(self):
        ev=buy_scenario()["events"][:3]+[
            {"date":DAYS[0],"type":"SELL_SUBMIT","shares":100,"limit":"9.80"}]
        x=simulation(buy_scenario(ev))
        self.assertEqual(x["reason"],"T_PLUS_ONE_OR_INSUFFICIENT_SETTLED_SHARES")
        self.assertNotIn("simulation_events",x)

    def test_cancel_unfilled_buy_then_new_order(self):
        ev=[
            {"date":DAYS[0],"type":"BUY_SUBMIT","shares":200,"limit":"10.00"},
            {"date":DAYS[0],"type":"BUY_FILL","shares":100,"price":"9.98"},
            {"date":DAYS[0],"type":"BUY_CANCEL"}
        ]
        x=simulation(buy_scenario(ev))
        self.assertEqual(x["remaining_shares"],100)
        self.assertIsNone(x["open_simulated_order"])
        self.assertEqual(x["simulation_events"][-1]["state"],"BUY_REMAINDER_CANCELLED")

    def test_buy_limit_must_not_be_exceeded(self):
        ev=[
            {"date":DAYS[0],"type":"BUY_SUBMIT","shares":100,"limit":"10.00"},
            {"date":DAYS[0],"type":"BUY_FILL","shares":100,"price":"10.01"}
        ]
        self.assertEqual(simulation(buy_scenario(ev))["reason"],
                         "BUY_FILL_OUTSIDE_LIMIT_OR_REMAINING")

    def test_sell_limit_must_not_be_undercut(self):
        ev=buy_scenario()["events"][:3]+[
            {"date":DAYS[1],"type":"SELL_SUBMIT","shares":200,"limit":"10.30"},
            {"date":DAYS[1],"type":"SELL_FILL","shares":200,"price":"10.29"}]
        self.assertEqual(simulation(buy_scenario(ev))["reason"],
                         "SELL_FILL_OUTSIDE_LIMIT_OR_SETTLED_SHARES")

    def test_partial_cancel_and_later_sell(self):
        ev=buy_scenario()["events"][:3]+[
            {"date":DAYS[1],"type":"SELL_SUBMIT","shares":200,"limit":"10.30"},
            {"date":DAYS[1],"type":"SELL_FILL","shares":100,"price":"10.30"},
            {"date":DAYS[1],"type":"SELL_CANCEL"},
            {"date":DAYS[2],"type":"SELL_SUBMIT","shares":100,"limit":"10.35"},
            {"date":DAYS[2],"type":"SELL_FILL","shares":100,"price":"10.35"}]
        x=simulation(buy_scenario(ev))
        self.assertEqual(x["remaining_shares"],0)
        self.assertIsNone(x["open_simulated_order"])

    def test_same_bar_touch_without_ordering_evidence_rejected(self):
        ev=buy_scenario()["events"][:3]+[
            {"date":DAYS[3],"type":"EXIT_TRIGGER","reason":"STOP_LOSS",
             "same_bar_both_touched":True}]
        self.assertEqual(simulation(buy_scenario(ev))["reason"],
                         "AMBIGUOUS_INTRABAR_EXIT")
        ev[-1].pop("same_bar_both_touched")
        self.assertEqual(simulation(buy_scenario(ev))["reason"],
                         "AMBIGUOUS_INTRABAR_EXIT")

    def test_time_exit_window_must_be_three_to_five_market_days(self):
        for day in (DAYS[1],DAYS[2]):
            with self.subTest(day=day):
                ev=buy_scenario()["events"][:3]+[
                    {"date":day,"type":"EXIT_TRIGGER","reason":"TIME_EXIT",
                     "same_bar_both_touched":False}]
                self.assertEqual(simulation(buy_scenario(ev))["reason"],
                                 "TIME_EXIT_NOT_3_TO_5_TRADING_DAYS")
        ev=buy_scenario()["events"][:3]+[
            {"date":DAYS[5],"type":"EXIT_TRIGGER","reason":"TIME_EXIT",
             "same_bar_both_touched":False}]
        self.assertEqual(simulation(buy_scenario(ev))["status"],
                         "OFFLINE_SCENARIO_REPLAYED_NOT_EXECUTABLE")

    def test_unsafe_market_or_data_rejected(self):
        for change in ({"code":"300015"},{"code":"688001"},{"is_st":None},
                       {"halted":True},{"initial_cash_cny":"NaN"},
                       {"trading_dates":DAYS[::-1]},
                       {"trading_dates":DAYS+[DAYS[-1]]}):
            with self.subTest(change=change):
                s=buy_scenario();s.update(change)
                x=simulation(s)
                self.assertEqual(x["status"],"REJECTED")
                self.assertEqual(x["trade_gate"],"BLOCKED")
                self.assertEqual(x["orders"],[])

    def test_overbuy_not_funded_and_fractional_buy_lot(self):
        ev=[{"date":DAYS[0],"type":"BUY_SUBMIT","shares":900,"limit":"10.00"}]
        self.assertEqual(simulation(buy_scenario(ev))["reason"],
                         "BUY_ORDER_EXCEEDS_CASH")
        ev[0]["shares"]=50
        self.assertEqual(simulation(buy_scenario(ev))["reason"],"BUY_LOT_NOT_100")

    def test_no_implicit_stop_fill(self):
        ev=buy_scenario()["events"][:3]+[
            {"date":DAYS[1],"type":"EXIT_TRIGGER","reason":"STOP_LOSS",
             "same_bar_both_touched":False}]
        x=simulation(buy_scenario(ev))
        self.assertEqual(x["remaining_shares"],200)
        self.assertTrue(x["exit_intent_observed"])
        self.assertFalse(x["simulated_fill_verified"])
        self.assertEqual(x["orders"],[])

if __name__=="__main__":unittest.main()
