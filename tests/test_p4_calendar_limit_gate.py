import unittest
from collector.p4_calendar_limit_gate import check_execution
class CalendarGateTests(unittest.TestCase):
    def base(self):
        return dict(entry_day="2026-10-19",exit_day="2026-10-20",calendar_sessions=["2026-10-19","2026-10-20"],security_limit_up="11",security_limit_down="9",observed_low="9.5",observed_high="10.5",side="SELL",order_limit_price="10")
    def test_ohlc_never_implies_fill(self):
        x=check_execution(**self.base())
        self.assertEqual(x["outcome"],"OHLC_NOT_EXECUTION_EVIDENCE")
        self.assertFalse(x["recorded_fill"])
    def test_limit_down_sell_block(self):
        x=check_execution(**{**self.base(),"observed_low":"9","observed_high":"9"})
        self.assertEqual(x["outcome"],"LIMIT_DOWN_NO_FILL_ASSUMPTION")
    def test_limit_up_buy_block(self):
        x=check_execution(**{**self.base(),"side":"BUY","observed_low":"11","observed_high":"11"})
        self.assertEqual(x["outcome"],"LIMIT_UP_NO_FILL_ASSUMPTION")
    def test_bad_calendar_rejected(self):
        with self.assertRaises(ValueError):check_execution(**{**self.base(),"calendar_sessions":["2026-10-20"]})
    def test_evidence_is_not_fill(self):
        x=check_execution(**{**self.base(),"orderbook_fill_evidence":True})
        self.assertFalse(x["recorded_fill"])
        self.assertEqual(x["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
