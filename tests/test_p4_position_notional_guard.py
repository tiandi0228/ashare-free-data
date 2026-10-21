"""Synthetic-only position-notional risk policy independent of private P4 strategy."""
import unittest
from decimal import Decimal
from collector.p4_position_notional_guard import check, fees

class PositionBudgetTests(unittest.TestCase):
    def case(self, stop="9.50", qty=400, market="SH", **extra):
        return {"synthetic_test_case": True,"market":market,
                "shares":qty,"entry_actual_fill":"10.00",
                "stop_exit_actual_fill":stop, **extra}

    def test_old_account_equity_three_percent_misses_position_limit(self):
        result=check(self.case())
        self.assertEqual(result["old_account_three_percent_cap_for_comparison_only_yuan"],"240.00")
        self.assertEqual(result["position_three_percent_risk_cap_yuan"],"120.00")
        self.assertEqual(result["modeled_net_stop_loss_yuan"],"211.98")
        self.assertFalse(result["synthetic_policy_pass"])
        self.assertEqual(result["risk_denominator"],"POSITION_BUY_NOTIONAL_NOT_ACCOUNT_EQUITY")
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertFalse(result["actual_fill_evidence"])

    def test_narrower_stop_with_fees_can_satisfy_notional_budget_but_not_authorize(self):
        r=check(self.case(stop="9.80"))
        self.assertTrue(r["synthetic_policy_pass"])
        self.assertTrue(r["within_position_three_percent_stop_budget"])
        self.assertLessEqual(Decimal(r["modeled_net_stop_loss_yuan"]),
                             Decimal(r["position_three_percent_risk_cap_yuan"]))
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["p4_out_of_sample_performance_validated"])
        self.assertFalse(r["risk_limit_guaranteed_against_gaps_or_halts"])

    def test_gap_actual_exit_price_must_include_adverse_move_once(self):
        a=check(self.case(stop="9.80"))
        b=check(self.case(stop="9.40"))
        self.assertGreater(Decimal(b["modeled_net_stop_loss_yuan"]),
                           Decimal(a["modeled_net_stop_loss_yuan"]))
        self.assertTrue(b["slippage_already_in_actual_fill_prices"])
        self.assertFalse(b["within_position_three_percent_stop_budget"])

    def test_duplicate_slippage_cost_field_forbidden(self):
        with self.assertRaisesRegex(ValueError,"duplicate slippage"):
            check(self.case(stop="9.80",slippage_fee="3.00"))

    def test_no_live_codes_or_real_market_scenarios(self):
        with self.assertRaisesRegex(ValueError,"No ticker"):
            check(self.case(ticker="600000"))
        with self.assertRaisesRegex(ValueError,"No live"):
            check({"market":"SH","shares":100,"entry_actual_fill":"10.00",
                   "stop_exit_actual_fill":"9.90"})

    def test_lots_ticks_price_and_finite_inputs(self):
        for case in (self.case(qty=101),self.case(stop="9.805"),
                     self.case(stop="10.00"),self.case(stop="NaN")):
            with self.subTest(case=case),self.assertRaises(ValueError):
                check(case)

    def test_small_positions_limited_by_fee_minimum(self):
        r=check(self.case(stop="9.99",qty=100))
        self.assertEqual(r["position_three_percent_risk_cap_yuan"],"30.00")
        self.assertGreater(Decimal(r["modeled_net_stop_loss_yuan"]),Decimal("10.00"))
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_buy_cash_cannot_exceed_model_account(self):
        r=check(self.case(stop="9.80",qty=800))
        self.assertFalse(r["within_cash_budget"])  # 8000 plus commission
        self.assertFalse(r["synthetic_policy_pass"])

    def test_shanghai_and_shenzhen_fee_tariffs_explicitly_provisional(self):
        self.assertEqual(fees(Decimal("4000"),"SH","BUY"),Decimal("5.04"))
        self.assertEqual(fees(Decimal("4000"),"SZ","BUY"),Decimal("5.00"))
        self.assertEqual(fees(Decimal("3800"),"SH","SELL"),Decimal("6.94"))

if __name__=="__main__":
    unittest.main()
