"""Offline performance is never a historical strategy result or a trade."""
import copy
import unittest
from collector.p2_offline_performance_ledger import evaluate

def case(id,dates,sell_price,stop_reason="TIME_EXIT"):
    buy,exitday=dates[0],dates[3]
    return {"id":id,"scenario":{
        "code":"002249","is_st":False,"halted":False,
        "initial_cash_cny":"8000.00","trading_dates":dates,
        "events":[
            {"type":"BUY_SUBMIT","date":buy,"limit":"10.00","shares":100},
            {"type":"BUY_FILL","date":buy,"price":"10.00","shares":100,
             "bar_time":buy+"T10:00:00+08:00"},
            {"type":"EXIT_TRIGGER","date":exitday,"reason":stop_reason,
             "same_bar_both_touched":False},
            {"type":"SELL_SUBMIT","date":exitday,"limit":sell_price,"shares":100},
            {"type":"SELL_FILL","date":exitday,"price":sell_price,"shares":100,
             "bar_time":exitday+"T10:00:00+08:00"},
        ]},
        "bars":{
            "code":"002249","is_st":False,"halted":False,
            "bars":[{
               "time":date+"T10:00:00+08:00",
               "open":price,"low":price,"high":price,"close":price,
               "volume_shares":1000,"is_final":True,
               "daily_lower_limit":"9.00","daily_upper_limit":"11.00"
            } for date,price in ((buy,"10.00"),(exitday,sell_price))]
        }}

D1=["2026-11-02","2026-11-03","2026-11-04","2026-11-05"]
D2=["2026-11-06","2026-11-09","2026-11-10","2026-11-11"]
def two():
    return {"initial_capital_cny":"8000","cases":[
        case("gain",D1,"10.50"),case("loss",D2,"9.80")
    ]}

class OfflinePerformanceTests(unittest.TestCase):
    def test_two_closed_trades_have_fee_inclusive_summary(self):
        r=evaluate(two())
        self.assertEqual(r["status"],"OFFLINE_CLOSED_SCENARIOS_ONLY_NOT_CERTIFIED")
        self.assertEqual(r["case_count"],2)
        self.assertEqual(r["win_count"],1)
        self.assertEqual(r["loss_count"],1)
        self.assertEqual(r["win_rate_pct"],"50.00")
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertFalse(r["strategy_backtest_certified"])
        self.assertFalse(r["simulated_fill_verified"])
        self.assertNotEqual(r["max_closed_trade_drawdown_pct"],"0.0000")
        self.assertEqual(len(r["realized_equity_curve"]),2)
    def test_unclosed_position_rejected_no_partial_statistics(self):
        p=two()
        p["cases"][0]["scenario"]["events"]=p["cases"][0]["scenario"]["events"][:2]
        r=evaluate(p)
        self.assertEqual(r["reason"],"INCOMPLETE_POSITION_OR_ORDER")
        self.assertNotIn("realized_equity_curve",r)
    def test_missing_exit_intent_is_not_counted(self):
        p=two()
        del p["cases"][0]["scenario"]["events"][2]
        self.assertEqual(evaluate(p)["reason"],"EXIT_REASON_NOT_RECORDED")
    def test_bad_price_evidence_rejected(self):
        p=two()
        p["cases"][0]["bars"]["bars"][1]["high"]="10.40"
        self.assertEqual(evaluate(p)["reason"],"FILL_BAR_EVIDENCE_NOT_PLAUSIBLE")
    def test_duplicate_ids_and_overlapping_cases_rejected(self):
        p=two()
        p["cases"][1]["id"]="gain"
        self.assertEqual(evaluate(p)["reason"],"DUPLICATE_CASE_ID")
        p=two()
        p["cases"][1]=case("overlap",D1,"10.20")
        self.assertEqual(evaluate(p)["reason"],"OVERLAPPING_OR_UNORDERED_CASES")
    def test_no_losses_profit_factor_explicitly_unavailable(self):
        p=two()
        p["cases"][1]=case("another_gain",D2,"10.40")
        r=evaluate(p)
        self.assertIsNone(r["profit_factor"])
        self.assertEqual(r["profit_factor_reason"],"NO_LOSING_CLOSED_SCENARIOS")
    def test_reject_bad_capital_or_missing_cases(self):
        for p in (None,{},{"initial_capital_cny":"NaN","cases":[case("one",D1,"10.50")]},
                  {"initial_capital_cny":"8000","cases":[]},
                  {"initial_capital_cny":"8000","cases":[case("one",D1,"10.50")]*41}):
            with self.subTest(p=p):
                r=evaluate(p)
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
