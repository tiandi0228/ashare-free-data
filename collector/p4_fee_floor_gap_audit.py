"""Source-linked fee-floor explanation of frozen P4 price-proxy barriers.

Never treats observed future vendor price rows as fills or builds a strategy.
Replays the existing immutable 2% stop / 5% target, 100-share lot, 8,000 CNY
budget and 10 bps per-side *assumed* friction. Exposes reasons the hypothetical
2:1 threshold fails, plus an INVERSE TARGET DISTANCE diagnostic, not forecasts.
"""
import argparse
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path

from collector.p4_observed_fee_friction import CAPITAL, CENT, exposure
from collector.p4_tplus1_barrier_touch import (
    BPS, MAX_RISK, PHASE as BARRIER_PHASE, barrier, positive
)

PHASE = "P4_FROZEN_STOP_TARGET_FEE_FLOOR_EXPLANATION"
SHA = re.compile(r"[0-9a-f]{40}\Z")
ISSUER = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
CATEGORIES = ("at_or_below_5pct", "above_5_to_7pct",
              "above_7_to_10pct", "above_10_to_15pct",
              "above_15_to_30pct", "above_30pct_or_unknown")
CHECK_KEYS = (
    "one_lot_cash_cap_passed", "one_lot_exceeds_cash_cap",
    "unusable_nonpositive_proxy_risk",
    "modelled_stop_risk_within_3pct_cash_cap",
    "modelled_reward_at_least_2x_stop_risk",
    "both_theoretical_barrier_thresholds_met",
)


def minimal_target(entry, issuer, needed, max_pct=Decimal("0.30")):
    """Find minimum tick for model reward >= 2x stop model risk.

    Diagnostic target does not mean the market will reach or fill at that
    target. Do not change 5% frozen backtest configuration from this value.
    """
    if entry <= 0 or needed <= 0:
        raise ValueError("invalid inverse target input")
    left = int((entry / CENT).to_integral_value(rounding=ROUND_FLOOR)) + 1
    right = int((entry*(1+max_pct)/CENT).to_integral_value(
        rounding=ROUND_CEILING))
    if right < left:
        return None
    def passes(n):
        return exposure(entry, Decimal(n)*CENT, issuer, BPS)[
            "modelled_margin_after_friction_cny"] >= needed
    if not passes(right):
        return None
    while left < right:
        mid = (left+right)//2
        if passes(mid):
            right = mid
        else:
            left = mid+1
    found = Decimal(left)*CENT
    if found <= entry or not passes(left):
        raise ValueError("inverse fee model not monotonic")
    return found


def band(increase):
    if increase is None:
        return CATEGORIES[-1]
    for cap, label in zip(
        (Decimal("5"), Decimal("7"), Decimal("10"),
         Decimal("15"), Decimal("30")), CATEGORIES[:5]
    ):
        if increase <= cap:
            return label
    return CATEGORIES[-1]


def audit(proxy, barriers):
    base = {
        "phase": PHASE, "status": "REJECTED", "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
        "historical_PIT_verified": False, "historical_OOS_validated": False,
        "strategy_backtest_certified": False, "trade_authorized": False,
        "fills_assumed": 0, "broker_trades_verified": 0,
        "slippage_observed": False, "historical_success_rate_claimed": False,
    }

    def fail(reason):
        return dict(base, reason=reason)

    try:
        if (not isinstance(proxy, dict) or not isinstance(barriers, dict)
                or proxy.get("phase") != "P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES"
                or proxy.get("status") != "OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST"
                or barriers.get("phase") != BARRIER_PHASE
                or barriers.get("status") != "TPLUS1_BARRIER_TOUCHES_NOT_EXECUTABLE_BACKTEST"
                or not isinstance(proxy.get("archive_commit_sha"), str)
                or not SHA.fullmatch(proxy["archive_commit_sha"])
                or barriers.get("archive_commit_sha") != proxy["archive_commit_sha"]
                or proxy.get("trade_gate") != "BLOCKED"
                or barriers.get("trade_gate") != "BLOCKED"
                or proxy.get("orders") != [] or barriers.get("orders") != []
                or proxy.get("executable_candidates") != []
                or barriers.get("executable_candidates") != []
                or proxy.get("actionable_buy_signals") != []
                or barriers.get("actionable_buy_signals") != []
                or proxy.get("historical_PIT_verified") is not False
                or barriers.get("historical_PIT_verified") is not False
                or proxy.get("historical_OOS_validated") is not False
                or barriers.get("historical_OOS_validated") is not False
                or barriers.get("trade_authorized") is not False
                or proxy.get("fills_assumed") != 0
                or barriers.get("fills_assumed") != 0):
            return fail("UNSAFE_OR_UNLINKED_UPSTREAM_PRICE_RESEARCH")
        assumptions = barriers.get("hypothetical_barriers")
        if (not isinstance(assumptions, dict)
                or assumptions.get("stop_percent_gross") != "2.00"
                or assumptions.get("target_percent_gross") != "5.00"
                or assumptions.get("assumed_slippage_bps_per_side") != BPS
                or assumptions.get("research_cash_limit_cny") != str(CAPITAL)
                or assumptions.get("research_risk_cap_cny") != str(MAX_RISK)
                or assumptions.get("minimum_100_share_lot") != 100):
            return fail("FROZEN_BARRIER_OR_FEE_MODEL_CHANGED")
        pairs = proxy.get("observed_price_pairs")
        declared = proxy.get("observed_next_open_to_third_close")
        if (not isinstance(pairs, list) or type(declared) is not int
                or not 0 <= declared <= 50000 or len(pairs) != declared
                or barriers.get("source_verified_mature_price_pairs") != declared):
            return fail("TRUNCATED_OR_MISMATCHED_OBSERVED_EVENT_SET")
        counters = Counter()
        buckets = Counter()
        samples = []
        seen = set()
        for pair in pairs:
            if not isinstance(pair, dict):
                return fail("INVALID_PRICE_PAIR")
            code, day = pair.get("issuer"), pair.get("signal_known_after_close_date")
            if (not isinstance(code, str) or not ISSUER.fullmatch(code)
                    or not isinstance(day, str) or
                    (code, day) in seen
                    or pair.get("next_open_fill_assumed") is not False
                    or pair.get("exit_close_fill_assumed") is not False
                    or pair.get("T_plus_1_execution_verified") is not False
                    or pair.get("trade_return") is not None):
                return fail("FORGED_EXECUTION_OR_DUPLICATE_MAINBOARD_EVENT")
            seen.add((code, day))
            entry = positive(pair.get("next_vendor_open"))
            stop, target = barrier(entry)
            counters["observed_pairs"] += 1
            if not exposure(entry, target, code, BPS)["affordable_one_lot_proxy"]:
                counters["one_lot_exceeds_cash_cap"] += 1
                continue
            counters["one_lot_cash_cap_passed"] += 1
            risk = -exposure(entry, stop, code, BPS)[
                "modelled_margin_after_friction_cny"]
            reward = exposure(entry, target, code, BPS)[
                "modelled_margin_after_friction_cny"]
            if risk <= 0:
                counters["unusable_nonpositive_proxy_risk"] += 1
                continue
            if risk <= MAX_RISK:
                counters["modelled_stop_risk_within_3pct_cash_cap"] += 1
            if reward >= 2*risk:
                counters["modelled_reward_at_least_2x_stop_risk"] += 1
            if risk <= MAX_RISK and reward >= 2*risk:
                counters["both_theoretical_barrier_thresholds_met"] += 1
            gross_risk = (entry-stop)*Decimal(100)
            gross_reward = (target-entry)*Decimal(100)
            if gross_reward >= 2*gross_risk and reward < 2*risk:
                counters["gross_2to1_erased_by_modelled_friction"] += 1
            elif gross_reward < 2*gross_risk:
                counters["gross_barriers_already_below_2to1"] += 1
            else:
                counters["frozen_5pct_net_2to1_passes"] += 1
            required = minimal_target(entry, code, 2*risk)
            increase = ((required/entry-1)*100) if required is not None else None
            buckets[band(increase)] += 1
            if len(samples) < 5:
                samples.append({
                    "issuer": code, "signal_completed_day": day,
                    "observed_vendor_entry_open_not_a_fill": str(entry),
                    "frozen_stop_price": str(stop),
                    "frozen_target_price": str(target),
                    "modelled_stop_risk_cny": str(risk),
                    "modelled_frozen_target_margin_cny": str(reward),
                    "hypothetical_minimum_target_for_2to1_not_forecast":
                        str(required) if required is not None else None,
                    "not_an_executable_order": True,
                })
        target = barriers.get("theoretical_friction_plan_checks")
        if (not isinstance(target, dict) or
                any(type(target.get(k)) is not int or target[k] != counters[k]
                    for k in CHECK_KEYS)):
            return fail("INDEPENDENT_FEE_AND_RISK_COUNTS_MISMATCH")
        modeled = (counters["one_lot_cash_cap_passed"]-
                   counters["unusable_nonpositive_proxy_risk"])
        if (sum(buckets.values()) != modeled or
                counters["frozen_5pct_net_2to1_passes"] !=
                counters["modelled_reward_at_least_2x_stop_risk"] or
                counters["gross_2to1_erased_by_modelled_friction"]+
                counters["gross_barriers_already_below_2to1"]+
                counters["frozen_5pct_net_2to1_passes"] != modeled):
            return fail("UNRECONCILED_MODELLED_FEE_BUCKETS")
        return dict(base,
            status="MODELLED_FEE_BARRIER_GAP_EXPLAINED_NO_BACKTEST",
            archive_commit_sha=proxy["archive_commit_sha"],
            source_verified_price_pairs=declared,
            cash_eligible_observation_pairs=counters["one_lot_cash_cap_passed"],
            source_frozen_5pct_reward_risk_passes=
                counters["modelled_reward_at_least_2x_stop_risk"],
            gross_2to1_erased_by_modelled_friction=
                counters["gross_2to1_erased_by_modelled_friction"],
            gross_barriers_already_below_2to1=
                counters["gross_barriers_already_below_2to1"],
            target_distance_to_modelled_2to1_buckets={
                k:buckets[k] for k in CATEGORIES},
            modelled_inverse_target_cap="30% above hypothetical vendor entry open",
            fee_floor_assumptions={
                "per_side_assumed_slippage_bps":BPS,
                "stop_percent_gross":"2.00",
                "target_percent_gross":"5.00",
                "lot_shares":100,
                "capital_cny":str(CAPITAL),
                "max_stop_model_risk_cny":str(MAX_RISK),
            },
            sample_non_executable_price_diagnostics=samples,
            limitations=[
                "TARGET_DISTANCE_IS_ALGEBRA_NOT_PRICE_REACHABILITY",
                "PRICE_LIMIT_BANDS_AND_LIQUIDITY_NOT_CERTIFIED",
                "NO_ACTUAL_ORDERS_OR_FILLS",
                "NO_STRATEGY_OPTIMIZATION_OR_OOS_VALIDATION",
                "SOURCE_HISTORICAL_PIT_AND_ISSUER_STATE_NOT_CERTIFIED",
            ])
    except (KeyError, ValueError, TypeError, ArithmeticError,
            InvalidOperation, OverflowError):
        return fail("INVALID_OR_NON_FINITE_SOURCE_PRICE_OR_MODEL")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--proxy",required=True)
    p.add_argument("--barriers",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    try:
        source=json.loads(Path(args.proxy).read_text())
        barriers=json.loads(Path(args.barriers).read_text())
        result=audit(source,barriers)
    except (ValueError,OSError,UnicodeError):
        result=audit(None,None)
    dst=Path(args.out)
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        k:result.get(k) for k in (
            "status","source_verified_price_pairs","cash_eligible_observation_pairs",
            "source_frozen_5pct_reward_risk_passes",
            "gross_2to1_erased_by_modelled_friction",
            "target_distance_to_modelled_2to1_buckets","trade_gate")
    },ensure_ascii=False))
    if result["status"]=="REJECTED":
        raise SystemExit(1)


if __name__=="__main__":
    main()
