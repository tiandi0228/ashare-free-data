"""Synthetic-only order state contract: fail closed on unverified fills/limits."""
import unittest
from collector.p4_synthetic_t1_execution_kernel import (
    replay, costs, price, contract_summary, PROVENANCE
)
from decimal import Decimal


def scenario(events,code="sh.600000"):
    return {"provenance":PROVENANCE,"trade_gate":"BLOCKED","orders":[],
            "issuer":code,"historical_PIT_verified":False,
            "real_liquidity_authenticated":False,
            "events":events}


def ev(day,kind,**kwargs):
    return {"session":day,"kind":kind,**kwargs}


MON="2026-11-02"
TUE="2026-11-03"
WED="2026-11-04"
THU="2026-11-05"
FRI="2026-11-06"
SYNTH="SYNTHETIC_MATCHING_FIXTURE"


class SyntheticT1ExecutionTests(unittest.TestCase):
    def assert_blocked(self,r):
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["real_broker_orders"],0)
        self.assertEqual(r["real_broker_fills"],0)
        self.assertFalse(r["historical_PIT_verified"])
        self.assertFalse(r["strategy_backtest_certified"])
        self.assertFalse(r["trade_authorized"])

    def test_buy_partial_today_unsellable_then_tplus1_partial_exit(self):
        events=[
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=40,fill_price="9.99",origin=SYNTH),
            ev(MON,"FILL_BUY",quantity=60,fill_price="10.00",origin=SYNTH),
            ev(MON,"PLACE_SELL",quantity=100,limit_price="9.80",
               reason="FROZEN_STOP"),  # must reject same-day sale
            ev(TUE,"BEGIN_SESSION"),
            ev(TUE,"PLACE_SELL",quantity=100,limit_price="9.80",
               reason="FROZEN_STOP"),
            ev(TUE,"FILL_SELL",quantity=60,fill_price="9.81",origin=SYNTH),
            ev(TUE,"FILL_SELL",quantity=40,fill_price="9.80",origin=SYNTH),
        ]
        r=replay(scenario(events))
        self.assertEqual(r["status"],
            "SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED")
        self.assertEqual(r["synthetic_fill_count"],4)
        self.assertEqual(r["synthetic_position_shares"],0)
        self.assertEqual(r["synthetic_sellable_shares"],0)
        self.assertEqual(r["synthetic_open_order_remaining_shares"],0)
        self.assertIn("TPLUS1_OR_INSUFFICIENT_SELLABLE_POSITION",
                      r["synthetic_rejections"])
        # Fees charged independently per synthetic partial execution;
        # these are TEST cash values, NEVER observed trade PnL.
        buy=(Decimal(40)*Decimal("9.99")+
             costs(40,Decimal("9.99"),"BUY","sh.600000")+
             Decimal(60)*Decimal("10.00")+
             costs(60,Decimal("10.00"),"BUY","sh.600000"))
        sell=(Decimal(60)*Decimal("9.81")-
              costs(60,Decimal("9.81"),"SELL","sh.600000")+
              Decimal(40)*Decimal("9.80")-
              costs(40,Decimal("9.80"),"SELL","sh.600000"))
        self.assertEqual(Decimal(r["synthetic_cash_end_cny"]),
                         (Decimal(8000)-buy+sell).quantize(Decimal("0.01")))
        self.assert_blocked(r)

    def test_friday_forced_exit_partial_never_claims_position_closed(self):
        r=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(FRI,"BEGIN_SESSION"),
            ev(FRI,"PLACE_SELL",quantity=100,limit_price="9.80",
               reason="FRIDAY_FORCE"),
            ev(FRI,"FILL_SELL",quantity=40,fill_price="9.81",origin=SYNTH),
        ]))
        self.assertEqual(r["status"],
            "SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED")
        self.assertEqual(r["synthetic_position_shares"],60)
        self.assertEqual(r["synthetic_sellable_shares"],60)
        self.assertEqual(r["synthetic_open_order_remaining_shares"],60)
        self.assertIn("UNRESOLVED_SYNTHETIC_ORDER_NOT_A_FILL",
                      r["synthetic_rejections"])
        self.assert_blocked(r)

    def test_friday_explicit_close_partial_sell_does_not_hide_60_shares(self):
        r=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(FRI,"BEGIN_SESSION"),
            ev(FRI,"PLACE_SELL",quantity=100,limit_price="9.80",
               reason="FRIDAY_FORCE"),
            ev(FRI,"FILL_SELL",quantity=40,fill_price="9.81",origin=SYNTH),
            ev(FRI,"END_SESSION"),
        ]))
        self.assertEqual(r["status"],
                         "SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED")
        self.assertEqual(r["synthetic_friday_close_report_count"],1)
        audit=r["synthetic_friday_close_reports"][0]
        self.assertEqual(audit["synthetic_close_status"],
                         "SYNTHETIC_FRIDAY_UNFILLED_SELL_REMAINDER")
        self.assertEqual(audit["unliquidated_shares"],60)
        self.assertEqual(audit["open_sell_order_remaining_shares"],60)
        self.assertTrue(audit["accepted_friday_force_sell_order"])
        self.assertFalse(audit["real_friday_exit_fill_authenticated"])
        self.assertEqual(r["synthetic_friday_unattested_session_count"],0)
        self.assertFalse(r["synthetic_all_friday_sessions_proven_flat_in_fixture"])
        self.assertFalse(r["real_friday_liquidation_certified"])
        self.assertIn("FRIDAY_FLAT_POSITION_POLICY_BREACH_SYNTHETIC",
                      r["synthetic_rejections"])
        self.assert_blocked(r)

    def test_friday_close_without_any_exit_order_is_breach_not_liquidation(self):
        r=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(FRI,"BEGIN_SESSION"),
            ev(FRI,"END_SESSION"),
        ]))
        audit=r["synthetic_friday_close_reports"][0]
        self.assertEqual(audit["synthetic_close_status"],
                         "SYNTHETIC_FRIDAY_POSITION_WITHOUT_ACCEPTED_FORCE_EXIT")
        self.assertEqual(audit["unliquidated_shares"],100)
        self.assertFalse(audit["accepted_friday_force_sell_order"])
        self.assertFalse(r["synthetic_all_friday_sessions_proven_flat_in_fixture"])
        self.assertEqual(r["synthetic_position_shares"],100)
        self.assert_blocked(r)

    def test_friday_fully_synthetic_sold_is_flat_but_not_real_exit_proof(self):
        r=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(FRI,"BEGIN_SESSION"),
            ev(FRI,"PLACE_SELL",quantity=100,limit_price="9.80",
               reason="FRIDAY_FORCE"),
            ev(FRI,"FILL_SELL",quantity=100,fill_price="9.80",origin=SYNTH),
            ev(FRI,"END_SESSION"),
        ]))
        audit=r["synthetic_friday_close_reports"][0]
        self.assertEqual(audit["synthetic_close_status"],
                         "SYNTHETIC_FRIDAY_FLAT_NOT_REAL_EXIT_PROOF")
        self.assertTrue(r["synthetic_all_friday_sessions_proven_flat_in_fixture"])
        self.assertEqual(r["synthetic_position_shares"],0)
        self.assertEqual(r["real_friday_exit_authentication_count"],0)
        self.assertFalse(r["real_friday_liquidation_certified"])
        self.assertFalse(r["real_exchange_session_end_authenticated"])
        self.assert_blocked(r)

    def test_new_friday_buy_is_vetoed_with_zero_synthetic_fill(self):
        r=replay(scenario([
            ev(FRI,"BEGIN_SESSION"),
            ev(FRI,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(FRI,"END_SESSION"),
        ]))
        self.assertEqual(r["synthetic_fill_count"],0)
        self.assertEqual(r["synthetic_position_shares"],0)
        self.assertEqual(r["synthetic_friday_close_report_count"],1)
        self.assertIn("FRIDAY_NEW_BUY_BLOCKED_BY_FROZEN_POLICY",
                      r["synthetic_rejections"])
        self.assert_blocked(r)

    def test_explicit_friday_snapshot_required_before_rollover_with_position(self):
        events=[
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(FRI,"BEGIN_SESSION"),
        ]
        from datetime import timedelta
        following="2026-11-09"
        fail=replay(scenario(events+[ev(following,"BEGIN_SESSION")]))
        self.assertEqual(fail["status"],"REJECTED")
        self.assertEqual(fail["reason"],
                         "FRIDAY_POSITION_ROLLED_WITHOUT_CLOSE_RISK_SNAPSHOT")
        self.assert_blocked(fail)
        snap=replay(scenario(events+[
            ev(FRI,"END_SESSION"),ev(following,"BEGIN_SESSION")]))
        self.assertEqual(snap["status"],
                         "SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED")
        self.assertEqual(snap["synthetic_position_shares"],100)
        self.assertFalse(snap["synthetic_all_friday_sessions_proven_flat_in_fixture"])
        self.assertEqual(snap["synthetic_friday_close_reports"][0]
                         ["unliquidated_shares"],100)
        self.assert_blocked(snap)

    def test_after_session_close_no_fills_allowed_and_missing_friday_close_is_not_pass(self):
        prior=[
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(FRI,"BEGIN_SESSION"),
        ]
        r=replay(scenario(prior))
        self.assertEqual(r["synthetic_friday_unattested_session_count"],1)
        self.assertFalse(r["synthetic_all_friday_sessions_proven_flat_in_fixture"])
        self.assertIn("LAST_FRIDAY_CLOSE_SNAPSHOT_NOT_OBSERVED",
                      r["synthetic_rejections"])
        fail=replay(scenario(prior+[
            ev(FRI,"END_SESSION"),
            ev(FRI,"PLACE_SELL",quantity=100,limit_price="9.80",
               reason="FRIDAY_FORCE")
        ]))
        self.assertEqual(fail["status"],"REJECTED")
        self.assertEqual(fail["reason"],
                         "EVENT_AFTER_EXPLICIT_SYNTHETIC_SESSION_END")
        self.assert_blocked(fail)

    def test_cancelling_residual_buy_before_next_session_preserves_tplus1(self):
        r=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=40,fill_price="10.00",origin=SYNTH),
            ev(MON,"CANCEL"),
            ev(TUE,"BEGIN_SESSION"),
            ev(TUE,"PLACE_SELL",quantity=40,limit_price="9.00",
               reason="TIME_EXIT"),
            ev(TUE,"FILL_SELL",quantity=40,fill_price="9.50",origin=SYNTH),
        ]))
        self.assertEqual(r["synthetic_position_shares"],0)
        self.assertEqual(r["synthetic_fill_count"],2)
        self.assert_blocked(r)

    def test_unresolved_order_cannot_roll_session_without_cancel(self):
        r=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(TUE,"BEGIN_SESSION"),
        ]))
        self.assertEqual(r["status"],"REJECTED")
        self.assertEqual(r["reason"],"OPEN_ORDER_CARRIED_WITHOUT_EXPLICIT_POLICY")
        self.assert_blocked(r)

    def test_initial_buy_not_100_lot_and_insufficient_budget(self):
        bad=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=40,limit_price="10.00"),
        ]))
        self.assertEqual(bad["reason"],"INITIAL_A_SHARE_BUY_ORDER_NOT_100_SHARE_LOT")
        costly=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=1000,limit_price="10.00"),
        ]))
        self.assertIn("BUY_BUDGET_WITH_FULL_LIMIT_RESERVE",
                      costly["synthetic_rejections"])
        self.assertEqual(costly["synthetic_fill_count"],0)
        self.assert_blocked(costly)

    def test_limits_overfills_invalid_fill_origin_and_no_fill(self):
        for change,reason in [
            (dict(fill_price="10.01"),"BUY_EXECUTED_ABOVE_LIMIT"),
            (dict(quantity=101),"OVERFILL_SYNTHETIC_ORDER"),
            (dict(origin="REAL_BROKER"),"UNAUTHENTICATED_FILL_ORIGIN"),
        ]:
            with self.subTest(change=change):
                fill={"quantity":100,"fill_price":"10.00","origin":SYNTH}
                fill.update(change)
                r=replay(scenario([
                    ev(MON,"BEGIN_SESSION"),
                    ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
                    ev(MON,"FILL_BUY",**fill),
                ]))
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["reason"],reason)
                self.assert_blocked(r)
        nofill=replay(scenario([
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
        ]))
        self.assertEqual(nofill["synthetic_fill_count"],0)
        self.assertEqual(nofill["synthetic_open_order_remaining_shares"],100)
        self.assert_blocked(nofill)

    def test_sell_limit_and_partial_sell_unknown_broker_status(self):
        base=[
            ev(MON,"BEGIN_SESSION"),
            ev(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
            ev(MON,"FILL_BUY",quantity=100,fill_price="10.00",origin=SYNTH),
            ev(TUE,"BEGIN_SESSION"),
            ev(TUE,"PLACE_SELL",quantity=100,limit_price="10.30",
               reason="FROZEN_TARGET"),
        ]
        r=replay(scenario(base+[
            ev(TUE,"FILL_SELL",quantity=100,fill_price="10.29",origin=SYNTH),
        ]))
        self.assertEqual(r["reason"],"SELL_EXECUTED_BELOW_LIMIT")
        self.assert_blocked(r)
        nofill=replay(scenario(base))
        self.assertEqual(nofill["synthetic_position_shares"],100)
        self.assertEqual(nofill["synthetic_sellable_shares"],100)
        self.assertEqual(nofill["synthetic_fill_count"],1)
        self.assert_blocked(nofill)

    def test_real_vendor_or_false_pit_claims_are_rejected(self):
        for modification in [
            {"provenance":"REAL_VENDOR_OHLC"},
            {"trade_gate":"OPEN"},
            {"historical_PIT_verified":True},
            {"real_liquidity_authenticated":True},
            {"orders":[{"side":"BUY"}]},
            {"broker_execution_id":"REAL-123"},
            {"issuer":"sz.300001"},
        ]:
            with self.subTest(modification=modification):
                fixture=scenario([ev(MON,"BEGIN_SESSION")])
                fixture.update(modification)
                r=replay(fixture)
                self.assertEqual(r["status"],"REJECTED")
                self.assert_blocked(r)

    def test_synthetic_date_order_duplicate_session_and_nonfinite_price(self):
        for events in [
            [ev(MON,"BEGIN_SESSION"),ev(MON,"BEGIN_SESSION")],
            [ev(TUE,"BEGIN_SESSION"),ev(MON,"BEGIN_SESSION")],
            [ev("2026-11-07","BEGIN_SESSION")],
            [ev(MON,"BEGIN_SESSION"),
             ev(MON,"PLACE_BUY",quantity=100,limit_price="NaN")],
            [ev(MON,"BEGIN_SESSION"),
             ev(MON,"PLACE_BUY",quantity=100,limit_price="0")],
        ]:
            with self.subTest(events=events):
                r=replay(scenario(events))
                self.assertEqual(r["status"],"REJECTED")
                self.assert_blocked(r)

    def test_read_only_ci_contract_never_exposes_live_order(self):
        r=contract_summary()
        self.assertEqual(r["provenance"],PROVENANCE)
        self.assertEqual(r["verified_broker_fills"],0)
        self.assertFalse(r["historical_exchange_calendar_authenticated"])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertFalse(r["frozen_strategy_ready"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["real_friday_liquidation_certified"])
        self.assertTrue(r["friday_session_close_proof_required_in_future_executable_gate"])
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["trade_gate"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
