"""No-trade risk math tests. These figures are hypothetical, not live prices."""
import unittest
from collector.ashare_trade_risk_preflight import preflight,fee,D,money

def case(**kwargs):
    row=dict(code="002249",is_st=False,halted=False,holding_days=3,
             capital_cny="8000",entry="10.00",stop="9.80",target="10.60")
    row.update(kwargs);return row

class RiskPreflightTests(unittest.TestCase):
    def test_lot_and_net_fee_bound(self):
        x=preflight(case())
        self.assertEqual(x["status"],"MATHEMATICALLY_FEASIBLE_NOT_EXECUTABLE")
        self.assertEqual(x["shares"]%100,0)
        self.assertLessEqual(D(x["cash_required_cny"]),D("8000"))
        self.assertLessEqual(D(x["planned_net_loss_cny"]),D("240"))
        self.assertGreaterEqual(D(x["planned_net_reward_risk"]),D("2"))
        self.assertEqual(x["trade_gate"],"BLOCKED")
        self.assertFalse(x["buy_recommendations_authorized"])
        self.assertFalse(x["realtime_quote_verified"])
        self.assertEqual(x["orders"],[])
    def test_shanghai_transfer_and_sell_stamp(self):
        self.assertEqual(fee(D("10"),100,"buy","600000"),D("5.01"))
        self.assertEqual(fee(D("10"),100,"sell","600000"),D("5.51"))
        self.assertEqual(fee(D("10"),100,"buy","002249"),D("5.00"))
        self.assertEqual(fee(D("10"),100,"sell","002249"),D("5.50"))
    def test_minimum_commission_makes_small_account_unaffordable(self):
        x=preflight(case(capital_cny="1000"))
        self.assertEqual(x["status"],"REJECTED")
        self.assertEqual(x["reasons"],["NO_LOT_FITS_BUDGET_NET_RISK_AND_RR"])
    def test_entrepreneur_does_not_authorize_chinext_star_st_or_halt(self):
        for change in (dict(code="300015"),dict(code="688001"),
                       dict(code="830001"),dict(code="123456"),
                       dict(is_st=True),dict(is_st=None),
                       dict(halted=True),dict(holding_days=1)):
            with self.subTest(change=change):
                x=preflight(case(**change))
                self.assertEqual(x["status"],"REJECTED")
                self.assertEqual(x["trade_gate"],"BLOCKED")
    def test_price_order_or_bad_tick_rejected(self):
        for change in (dict(stop="10.00"),dict(target="9.95"),
                       dict(entry="10.001"),dict(entry="NaN"),
                       dict(stop="-2"),dict(entry=10.0),
                       dict(capital_cny="inf")):
            with self.subTest(change=change):
                self.assertEqual(preflight(case(**change))["status"],"REJECTED")
    def test_adequate_budget_but_insufficient_net_reward(self):
        x=preflight(case(target="10.30"))
        self.assertEqual(x["status"],"REJECTED")
        self.assertIn("NO_LOT_FITS_BUDGET_NET_RISK_AND_RR",x["reasons"])
    def test_invalid_input_always_blocked(self):
        for row in (None,{},[],{"code":"600000"},case(holding_days=True)):
            with self.subTest(row=row):
                x=preflight(row)
                self.assertEqual(x["status"],"REJECTED")
                self.assertEqual(x["orders"],[])
                self.assertEqual(x["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
