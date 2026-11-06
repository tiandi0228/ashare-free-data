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
                with self.assertRaises(ValueError):replay(**{**self.args(),**kwargs})
    def test_planned_stop_scenario(self):
        within=replay(**self.args(),planned_stop_price="9.85")
        outside=replay(**self.args(),planned_stop_price="9.70")
        self.assertTrue(within["planned_stop_risk_scenario"]["scenario_within_budget"])
        self.assertFalse(outside["planned_stop_risk_scenario"]["scenario_within_budget"])
        self.assertFalse(within["planned_stop_risk_scenario"]["stop_fill_verified"])
        self.assertEqual(within["trade_gate"],"BLOCKED")
        with self.assertRaises(ValueError):
            replay(**self.args(),planned_stop_price="11")
    def test_tplus1(self):
        with self.assertRaises(ValueError):replay(**{**self.args(),"sell_day":"2026-10-19"})
    def test_lot_and_nonpositive_price(self):
        with self.assertRaises(ValueError):replay(**{**self.args(),"shares":20})
        with self.assertRaises(ValueError):replay(**{**self.args(),"buy_price":"0"})
    def test_cash_limit_includes_commission_and_transfer(self):
        safe=replay(**self.args())
        self.assertTrue(safe["cash_budget_preflight_passed"])
        self.assertEqual(safe["cash_capital_limit"],"8000")
        # Buying exactly 8000 CNY of shares is NOT affordable when fees
        # are added; no research receipt may imply a feasible order.
        with self.assertRaisesRegex(ValueError,"exceeds available capital"):
            replay(**{**self.args(),"buy_price":"80"})
        with self.assertRaisesRegex(ValueError,"exceeds available capital"):
            replay(**{**self.args(),"shares":800})
        for value in ("0","NaN","Infinity","-100"):
            with self.subTest(capital_limit=value):
                with self.assertRaisesRegex(ValueError,"capital limit"):
                    replay(**self.args(),capital_limit=value)
        self.assertTrue(replay(**self.args(),capital_limit="1010")["cash_budget_preflight_passed"])
        with self.assertRaisesRegex(ValueError,"exceeds available capital"):
            replay(**self.args(),capital_limit="1000")

    def test_exchange_specific_transfer_fee_model(self):
        sh=replay(**self.args(),issuer="sh.600000")
        sz=replay(**self.args(),issuer="sz.000001")
        self.assertEqual(sh["issuer"],"sh.600000")
        self.assertEqual(sz["issuer"],"sz.000001")
        self.assertGreater(float(sh["buy_cost"]),float(sz["buy_cost"]))
        self.assertLess(float(sh["net_pnl"]),float(sz["net_pnl"]))
        for code in ("sh.688001","sz.300001","sh.000001","invalid"):
            with self.subTest(issuer=code):
                with self.assertRaisesRegex(ValueError,"mainboard issuer"):
                    replay(**self.args(),issuer=code)

    def test_fee_inclusive_stop_portfolio_and_position_budgets_are_distinct(self):
        result=replay(**self.args(),issuer="sz.000001",planned_stop_price="9.50")
        stop=result["planned_stop_risk_scenario"]
        self.assertFalse(stop["scenario_within_budget"])
        self.assertTrue(stop["scenario_within_portfolio_budget"])
        self.assertEqual(stop["portfolio_risk_budget_cny"],"240.00")
        self.assertFalse(stop["stop_fill_verified"])
        self.assertFalse(stop["gap_or_limit_down_covered"])
        assert result["trade_gate"]=="BLOCKED" and result["orders"]==[]
        very_low=replay(**self.args(),planned_stop_price="7.00")
        self.assertFalse(very_low["planned_stop_risk_scenario"]["scenario_within_portfolio_budget"])

    def test_max_risk_fraction(self):
        with self.assertRaises(ValueError):replay(**self.args(),risk_budget_fraction="0.1")
if __name__=="__main__":unittest.main()
