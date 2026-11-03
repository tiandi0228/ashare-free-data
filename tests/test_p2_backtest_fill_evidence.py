"""Fictitious fill events only; exact final bar checks cannot certify fills."""
import copy
import unittest
from collector.p2_backtest_fill_evidence import join
from collector.p2_offline_fill_machine import simulation

def scenario():
    return {
        "code":"002249","is_st":False,"halted":False,"initial_cash_cny":"8000",
        "trading_dates":["2026-11-02","2026-11-03","2026-11-04","2026-11-05"],
        "events":[
            {"type":"BUY_SUBMIT","date":"2026-11-02","shares":100,"limit":"10.00"},
            {"type":"BUY_FILL","date":"2026-11-02","shares":100,"price":"9.99",
             "bar_time":"2026-11-02T10:00:00+08:00"},
            {"type":"SELL_SUBMIT","date":"2026-11-05","shares":100,"limit":"10.25"},
            {"type":"SELL_FILL","date":"2026-11-05","shares":100,"price":"10.30",
             "bar_time":"2026-11-05T10:00:00+08:00"},
        ]}
def bars():
    rows=[]
    for day,op,lo,hi,cl in (
        ("2026-11-02","10.00","9.90","10.10","9.99"),
        ("2026-11-05","10.25","10.20","10.40","10.30")):
        rows.append({"time":day+"T10:00:00+08:00",
                     "open":op,"low":lo,"high":hi,"close":cl,
                     "daily_lower_limit":"9.00","daily_upper_limit":"11.00",
                     "volume_shares":1000,"is_final":True})
    return {"code":"002249","is_st":False,"halted":False,"bars":rows}

class BacktestEvidenceTests(unittest.TestCase):
    def test_consistent_bars_cannot_certify_exchange_fill(self):
        r=join(scenario(),bars())
        self.assertEqual(r["status"],"STRUCTURAL_REPLAY_PLAUSIBLE_NOT_EXECUTABLE")
        self.assertEqual(r["checked_explicit_fill_events"],2)
        self.assertEqual(r["checked_distinct_bars"],2)
        self.assertFalse(r["simulated_fill_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["executable_candidates"],[])
    def test_price_outside_bar_rejected(self):
        s=scenario();s["events"][1]["price"]="9.80"
        self.assertEqual(join(s,bars())["reason"],"FILL_PRICE_OUTSIDE_BAR_RANGE")
    def test_market_volume_bound_rejected(self):
        b=bars();b["bars"][0]["volume_shares"]=99
        self.assertEqual(join(scenario(),b)["reason"],
                         "FILL_SHARES_EXCEED_BAR_MARKET_VOLUME")
    def test_missing_or_other_day_bar_rejected(self):
        s=scenario();s["events"][1]["bar_time"]="2026-11-02T10:01:00+08:00"
        self.assertEqual(join(s,bars())["reason"],"NO_EXACT_FINAL_BAR_FOR_FILL")
        s=scenario();s["events"][1]["bar_time"]="2026-11-03T10:00:00+08:00"
        self.assertEqual(join(s,bars())["reason"],
                         "FILL_BAR_EVENT_TRADING_DAY_MISMATCH")
    def test_unfinalized_bar_rejected(self):
        b=bars();b["bars"][0]["is_final"]=False
        self.assertEqual(join(scenario(),b)["reason"],"BAR_PREFLIGHT_REJECTED")
    def test_bad_market_security_identity_rejected(self):
        b=bars();b["code"]="600000"
        self.assertEqual(join(scenario(),b)["reason"],
                         "SCENARIO_BAR_IDENTITY_MISMATCH")
    def test_intraday_timestamp_order_rejected(self):
        s=scenario()
        # Buy happens on Nov 2; a future-day labelled fill must not pass.
        s["events"][1]["bar_time"]="2026-11-05T10:00:00+08:00"
        self.assertEqual(join(s,bars())["reason"],
                         "FILL_BAR_EVENT_TRADING_DAY_MISMATCH")
    def test_replay_rejection_is_not_hidden(self):
        s=scenario();s["events"][3]["price"]="10.20"
        self.assertEqual(join(s,bars())["reason"],
                         "SIMULATED_EVENT_REPLAY_REJECTED")
    def test_orders_expire_at_next_trading_day(self):
        s=scenario();s["events"]=[
            {"type":"BUY_SUBMIT","date":"2026-11-02","shares":100,"limit":"10.00"},
            {"type":"BUY_FILL","date":"2026-11-03","shares":100,"price":"9.99"}]
        r=simulation(s)
        self.assertEqual(r["reason"],"PREVIOUS_DAY_ORDER_NOT_CLOSED")
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_partial_day_order_must_be_cancelled_before_next_day(self):
        s=scenario();s["events"]=[
            {"type":"BUY_SUBMIT","date":"2026-11-02","shares":200,"limit":"10.00"},
            {"type":"BUY_FILL","date":"2026-11-02","shares":100,"price":"9.99"},
            {"type":"SELL_SUBMIT","date":"2026-11-03","shares":100,"limit":"10.30"}]
        self.assertEqual(simulation(s)["reason"],"PREVIOUS_DAY_ORDER_NOT_CLOSED")
        s["events"].insert(2,{"type":"BUY_CANCEL","date":"2026-11-02"})
        self.assertEqual(simulation(s)["status"],
                         "OFFLINE_SCENARIO_REPLAYED_NOT_EXECUTABLE")
    def test_missing_inputs_fail_closed(self):
        for s,b in ((None,None),(scenario(),{}),(scenario(),None)):
            with self.subTest(s=s,b=b):
                r=join(s,b)
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["orders"],[])

if __name__=="__main__":unittest.main()
