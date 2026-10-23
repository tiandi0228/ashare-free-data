import unittest
from collector.p4_integrated_research_gate import verify

def fixture():
    return {"trade_gate":"BLOCKED","orders":[],
      "cost":{"buy_price":"10","sell_price":"10.5","shares":100,"buy_day":"2026-10-19","sell_day":"2026-10-20"},
      "exit":{"entry_day":"2026-10-19","observation_day":"2026-10-20","trading_sessions_elapsed":1,"low":9.5,"high":10.8,"stop":9.7,"take_profit":10.6,"tradable":True,"fill_proven":True},
      "calendar":{"entry_day":"2026-10-19","exit_day":"2026-10-20","calendar_sessions":["2026-10-19","2026-10-20"],"security_limit_up":"11","security_limit_down":"9","observed_low":"9.5","observed_high":"10.8","side":"SELL","order_limit_price":"10"},
      "signals":[{"signal_id":"x","trade_gate":"BLOCKED","orders":[],"source_observed_at":"2026-10-20T07:00:00+00:00","signal_completed_at":"2026-10-20T07:01:00+00:00","execution_status":"UNFILLED","fill":None}]}
class IntegratedTests(unittest.TestCase):
    def test_all_gates_research_only(self):
        result=verify(fixture())
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(result["strategy_backtest_completed"])
        self.assertFalse(result["historical_OOS_validated"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_bad_time_fails_pipeline(self):
        f=fixture();f["signals"][0]["source_observed_at"]="2026-10-20T07:02:00+00:00"
        with self.assertRaises(ValueError):verify(f)
    def test_bad_calendar_fails_pipeline(self):
        f=fixture();f["calendar"]["calendar_sessions"]=["2026-10-20"]
        with self.assertRaises(ValueError):verify(f)
if __name__=="__main__":unittest.main()
