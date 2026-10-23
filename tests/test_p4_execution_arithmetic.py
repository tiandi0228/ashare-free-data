import unittest
from collector.p4_execution_arithmetic import replay
class ExecutionTests(unittest.TestCase):
    def args(self):
        return dict(buy_price="10",sell_price="10",shares=100,buy_day="2026-10-19",sell_day="2026-10-20")
    def test_flat_trade_loses_fees(self):
        r=replay(**self.args())
        self.assertLess(float(r["net_pnl"]),0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertFalse(r["historical_OOS_validated"])
    def test_slippage_once(self):
        a=replay(**self.args())
        b=replay(**self.args(),slippage_buy="0.01",slippage_sell="0.01")
        self.assertLess(float(b["net_pnl"]),float(a["net_pnl"]))
    def test_reject_optimistic_negative_or_nonfinite_inputs(self):
        for kwargs in ({"slippage_buy":"-0.01"},{"slippage_sell":"-0.01"},{"slippage_buy":"NaN"},{"sell_price":"Infinity"},{"commission_rate":"NaN"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):replay(**self.args(),**kwargs)
    def test_tplus1(self):
        with self.assertRaises(ValueError):replay(**{**self.args(),"sell_day":"2026-10-19"})
    def test_lot_and_nonpositive_price(self):
        with self.assertRaises(ValueError):replay(**{**self.args(),"shares":20})
        with self.assertRaises(ValueError):replay(**{**self.args(),"buy_price":"0"})
    def test_max_risk_fraction(self):
        with self.assertRaises(ValueError):replay(**self.args(),risk_budget_fraction="0.1")
if __name__=="__main__":unittest.main()
