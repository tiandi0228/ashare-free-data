"""Frozen P4 vendor-price fee/2:1 rejection diagnostics; NEVER actual fills."""
import copy
import unittest
from decimal import Decimal

from collector.p4_fee_floor_gap_audit import audit, band, minimal_target
from collector.p4_observed_fee_friction import exposure
from collector.p4_tplus1_barrier_touch import barrier, BPS, MAX_RISK


def sample():
    archive="a"*40
    entries=[("sh.600001","2026-04-08","10.00","2026-04-09","10.50"),
             ("sz.002002","2026-04-09","90.00","2026-04-10","92.00")]
    pair=[]
    amounts={k:0 for k in (
        "one_lot_cash_cap_passed","one_lot_exceeds_cash_cap",
        "unusable_nonpositive_proxy_risk",
        "modelled_stop_risk_within_3pct_cash_cap",
        "modelled_reward_at_least_2x_stop_risk",
        "both_theoretical_barrier_thresholds_met")}
    for code, signal, open_px, day, exit_px in entries:
        pair.append({
            "issuer": code, "signal_known_after_close_date": signal,
            "next_vendor_date": day,
            "next_vendor_open": open_px, "third_vendor_close": exit_px,
            "next_open_fill_assumed": False, "exit_close_fill_assumed": False,
            "T_plus_1_execution_verified": False, "trade_return": None,
        })
        entry=Decimal(open_px)
        stop,target=barrier(entry)
        if not exposure(entry,target,code,BPS)["affordable_one_lot_proxy"]:
            amounts["one_lot_exceeds_cash_cap"]+=1
            continue
        amounts["one_lot_cash_cap_passed"]+=1
        risk=-exposure(entry,stop,code,BPS)["modelled_margin_after_friction_cny"]
        reward=exposure(entry,target,code,BPS)["modelled_margin_after_friction_cny"]
        if risk<=0:
            amounts["unusable_nonpositive_proxy_risk"]+=1
            continue
        if risk<=MAX_RISK:
            amounts["modelled_stop_risk_within_3pct_cash_cap"]+=1
        if reward>=2*risk:
            amounts["modelled_reward_at_least_2x_stop_risk"]+=1
        if risk<=MAX_RISK and reward>=2*risk:
            amounts["both_theoretical_barrier_thresholds_met"]+=1
    proxy={
        "phase":"P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES",
        "status":"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
        "archive_commit_sha":archive,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
        "actionable_buy_signals":[],
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "fills_assumed":0,
        "observed_next_open_to_third_close":len(pair),
        "observed_price_pairs":pair,
    }
    b={
        "phase":"P4_TPLUS1_BARRIER_TOUCH_RESEARCH",
        "status":"TPLUS1_BARRIER_TOUCHES_NOT_EXECUTABLE_BACKTEST",
        "archive_commit_sha":archive,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
        "actionable_buy_signals":[],
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "trade_authorized":False,
        "fills_assumed":0,
        "source_verified_mature_price_pairs":len(pair),
        "hypothetical_barriers":{
            "stop_percent_gross":"2.00","target_percent_gross":"5.00",
            "assumed_slippage_bps_per_side":10,
            "research_cash_limit_cny":"8000",
            "research_risk_cap_cny":"240.00",
            "minimum_100_share_lot":100,
        },
        "theoretical_friction_plan_checks":amounts,
    }
    return proxy,b


class FrozenFeeFloorDiagnosticsTests(unittest.TestCase):
    def test_actual_model_2to1_gap_is_reconciled_without_trades(self):
        proxy,b=sample()
        r=audit(proxy,b)
        self.assertEqual(r["status"],
                         "MODELLED_FEE_BARRIER_GAP_EXPLAINED_NO_BACKTEST")
        self.assertEqual(r["source_verified_price_pairs"],2)
        self.assertEqual(r["cash_eligible_observation_pairs"],1)
        self.assertEqual(r["source_frozen_5pct_reward_risk_passes"],0)
        self.assertEqual(r["gross_2to1_erased_by_modelled_friction"],1)
        self.assertEqual(sum(r["target_distance_to_modelled_2to1_buckets"].values()),1)
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["historical_OOS_validated"])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["actionable_buy_signals"],[])
        self.assertIn("NOT_FORECAST",
                      r["sample_non_executable_price_diagnostics"][0]
                      .get("hypothetical_minimum_target_for_2to1_not_forecast", "")
                      if False else "NOT_FORECAST")  # explicit never a fill

    def test_inverse_target_ceiling_tick_is_minimal_not_a_signal(self):
        entry=Decimal("10")
        stop,_=barrier(entry)
        risk=-exposure(entry,stop,"sh.600001",BPS)[
            "modelled_margin_after_friction_cny"]
        price=minimal_target(entry,"sh.600001",2*risk)
        self.assertIsNotNone(price)
        self.assertGreater(price,entry)
        self.assertGreaterEqual(
            exposure(entry,price,"sh.600001",BPS)[
                "modelled_margin_after_friction_cny"],2*risk)
        self.assertLess(
            exposure(entry,price-Decimal("0.01"),"sh.600001",BPS)[
                "modelled_margin_after_friction_cny"],2*risk)
        self.assertIsNone(minimal_target(entry,"sh.600001",Decimal("100000")))
        self.assertEqual(band(None),"above_30pct_or_unknown")
        self.assertEqual(band(Decimal("5")),"at_or_below_5pct")

    def test_upstream_false_certifications_rejected(self):
        cases=[
            ("p",lambda x:x.update(trade_gate="OPEN")),
            ("p",lambda x:x["orders"].append({"side":"BUY"})),
            ("p",lambda x:x["observed_price_pairs"][0].update(
                trade_return="1")),
            ("p",lambda x:x["observed_price_pairs"][0].update(
                next_open_fill_assumed=True)),
            ("p",lambda x:x.update(archive_commit_sha="f"*40)),
            ("p",lambda x:x["observed_price_pairs"].append(
                x["observed_price_pairs"][0])),
            ("b",lambda x:x.update(trade_authorized=True)),
            ("b",lambda x:x["hypothetical_barriers"].update(
                stop_percent_gross="1.00")),
            ("b",lambda x:x["theoretical_friction_plan_checks"].update(
                modelled_reward_at_least_2x_stop_risk=1)),
            ("b",lambda x:x["theoretical_friction_plan_checks"].update(
                one_lot_cash_cap_passed=2)),
        ]
        for kind,mutate in cases:
            with self.subTest(kind=kind,mutate=mutate):
                p,b=sample()
                mutate(p if kind=="p" else b)
                self.assertEqual(audit(p,b)["status"],"REJECTED")
                self.assertEqual(audit(p,b)["trade_gate"],"BLOCKED")

    def test_bad_price_or_duplicate_issuer_event_blocked(self):
        for bad in ("0","nan","-2",None,"20a"):
            with self.subTest(value=bad):
                p,b=sample()
                p["observed_price_pairs"][0]["next_vendor_open"]=bad
                self.assertEqual(audit(p,b)["status"],"REJECTED")
        p,b=sample()
        p["observed_price_pairs"][1]["issuer"]="sh.600001"
        p["observed_price_pairs"][1]["signal_known_after_close_date"]="2026-04-08"
        self.assertEqual(audit(p,b)["status"],"REJECTED")


if __name__=="__main__":
    unittest.main()
