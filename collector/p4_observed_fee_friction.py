"""Fee/friction sensitivity applied to audited vendor PRICE observations only.

No fills, orders, trading returns, stock recommendations, or historical PIT
certification. Models one 100-share hypothetical A-share round trip with a
frozen 8,000 CNY cash cap. The exit is a third later vendor close, not a fill.
The 0 and 10 basis-point-per-side assumptions are research scenarios, NOT
observed spreads or a claim about execution.
"""
import argparse
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_HALF_EVEN
from pathlib import Path

PHASE = "P4_OBSERVED_PRICE_FRICTION_SENSITIVITY"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
CENT = Decimal("0.01")
Q = Decimal("0.0001")
CAPITAL = Decimal("8000")
QUANTITY = Decimal("100")
COMMISSION = Decimal("0.0002854")
COMMISSION_FLOOR = Decimal("5")
STAMP_ON_SELL = Decimal("0.0005")
SH_TRANSFER = Decimal("0.00001")
BPS = (0, 10)


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def decimal(text):
    if not isinstance(text, str):
        raise ValueError("non-string observed price")
    result = Decimal(text)
    if not result.is_finite() or result <= 0:
        raise ValueError("invalid observed price")
    return result


def exposure(open_price, exit_price, issuer, bps):
    """Pure price-proxy scenario; never infers execution or trade PnL."""
    haircut = Decimal(bps) / Decimal(10000)
    entry_notional = QUANTITY * open_price * (1 + haircut)
    exit_notional = QUANTITY * exit_price * (1 - haircut)
    buy_commission = max(COMMISSION_FLOOR, money(entry_notional * COMMISSION))
    sell_commission = max(COMMISSION_FLOOR, money(exit_notional * COMMISSION))
    buy_transfer = money(entry_notional * SH_TRANSFER) if issuer.startswith("sh.") else Decimal(0)
    sell_transfer = money(exit_notional * SH_TRANSFER) if issuer.startswith("sh.") else Decimal(0)
    stamp = money(exit_notional * STAMP_ON_SELL)
    buy_cash = entry_notional + buy_commission + buy_transfer
    gross_observed_price_difference = QUANTITY * (exit_price - open_price)
    hypothetical_cost_adjusted_margin = (
        exit_notional - sell_commission - sell_transfer - stamp - buy_cash
    )
    drag = gross_observed_price_difference - hypothetical_cost_adjusted_margin
    return {
        "cash_required_at_proxy_entry_cny": money(buy_cash),
        "affordable_one_lot_proxy": buy_cash <= CAPITAL,
        "gross_observed_price_difference_cny": money(gross_observed_price_difference),
        "modelled_total_friction_cny": money(drag),
        "modelled_margin_after_friction_cny": money(hypothetical_cost_adjusted_margin),
        "entry_commission_cny": money(buy_commission),
        "exit_commission_cny": money(sell_commission),
        "exit_stamp_cny": money(stamp),
        "entry_transfer_cny": money(buy_transfer),
        "exit_transfer_cny": money(sell_transfer),
    }


def audit(proxy):
    base = {
        "phase": PHASE, "status": "REJECTED", "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
        "fills_assumed": 0, "trades_assumed": 0,
        "portfolio_pnl_computed": False, "trade_returns_computed": False,
        "strategy_backtest_certified": False, "historical_OOS_validated": False,
        "historical_PIT_verified": False, "risk_gate_verified": False,
        "trade_authorized": False,
    }

    def reject(reason):
        return dict(base, reason=reason)

    try:
        if (not isinstance(proxy, dict)
                or proxy.get("phase") != "P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES"
                or proxy.get("status") != "OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST"
                or proxy.get("trade_gate") != "BLOCKED"
                or proxy.get("orders") != []
                or proxy.get("executable_candidates") != []
                or proxy.get("actionable_buy_signals") != []
                or proxy.get("fills_assumed") != 0
                or proxy.get("trades_assumed") != 0
                or proxy.get("portfolio_pnl_computed") is not False
                or proxy.get("strategy_backtest_certified") is not False
                or proxy.get("historical_PIT_verified") is not False
                or proxy.get("historical_OOS_validated") is not False
                or not isinstance(proxy.get("archive_commit_sha"), str)
                or not COMMIT.fullmatch(proxy["archive_commit_sha"])):
            return reject("UNSAFE_PRICE_PROXY")
        cutoff = date.fromisoformat(proxy["holdout_cutoff_inclusive"])
        def count(name):
            value = proxy[name]
            if type(value) is not int or value < 0:
                raise ValueError("invalid counter")
            return value
        total = count("verified_nonoverlap_events")
        n = count("observed_next_open_to_third_close")
        censored = count("censored_events")
        blocked = count("future_vendor_status_blocked")
        expected_positive = count("positive_price_changes")
        expected_negative = count("negative_price_changes")
        expected_flat = count("flat_price_changes")
        if (total != n + censored + blocked
                or n != expected_positive + expected_negative + expected_flat):
            return reject("UNRECONCILED_EVENT_COUNTERS")
        rows = proxy.get("observed_price_pairs")
        if not isinstance(rows, list) or len(rows) != n or len(rows) > 50000:
            return reject("TRUNCATED_OR_UNBOUNDED_OBSERVATIONS")
        seen = set()
        directions = Counter()
        totals = {bps: Counter() for bps in BPS}
        sample = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                return reject("INVALID_OBSERVATION_ROW")
            code = row.get("issuer")
            if not isinstance(code, str) or not ISSUER.fullmatch(code):
                return reject("NON_MAINBOARD_OR_INVALID_ISSUER")
            if not isinstance(row.get("original_csv_sha256"), str) or not SHA.fullmatch(row["original_csv_sha256"]):
                return reject("UNPINNED_OBSERVATION_ROW")
            signal = date.fromisoformat(row["signal_known_after_close_date"])
            entry_day = date.fromisoformat(row["next_vendor_date"])
            exit_day = date.fromisoformat(row["third_vendor_date"])
            if not cutoff < signal < entry_day < exit_day:
                return reject("INVALID_OBSERVATION_TIME_ORDER")
            if (row.get("next_open_fill_assumed") is not False
                    or row.get("exit_close_fill_assumed") is not False
                    or row.get("trade_return") is not None
                    or row.get("T_plus_1_execution_verified") is not False):
                return reject("FORGED_EXECUTION_EVIDENCE")
            key = (code, signal.isoformat())
            if key in seen:
                return reject("DUPLICATE_ISSUER_EVENT")
            seen.add(key)
            signal_close = decimal(row["signal_close"])
            entry = decimal(row["next_vendor_open"])
            exit_price = decimal(row["third_vendor_close"])
            reported_delta = Decimal(row["next_open_to_third_close_change_pct"])
            reported_gap = Decimal(row["overnight_open_gap_pct"])
            if not (reported_delta.is_finite() and reported_gap.is_finite()):
                return reject("NONFINITE_REPORTED_CHANGE")
            actual_delta = (exit_price / entry - 1) * 100
            actual_gap = (entry / signal_close - 1) * 100
            if (actual_delta.quantize(Q, rounding=ROUND_HALF_EVEN) != reported_delta
                    or actual_gap.quantize(Q, rounding=ROUND_HALF_EVEN) != reported_gap):
                return reject("PRICE_CHANGE_NOT_IN_SOURCE")
            direction = "positive" if exit_price > entry else (
                "negative" if exit_price < entry else "flat")
            directions[direction] += 1
            audit_row = None
            for bps in BPS:
                model = exposure(entry, exit_price, code, bps)
                tracker = totals[bps]
                tracker["all_observed"] += 1
                if not model["affordable_one_lot_proxy"]:
                    tracker["one_lot_cash_cap_exceeded"] += 1
                    continue
                tracker["one_lot_cash_cap_passed"] += 1
                if direction == "positive":
                    tracker["observed_price_up_affordable"] += 1
                model_margin = model["modelled_margin_after_friction_cny"]
                if model_margin > 0:
                    tracker["positive_modelled_margin"] += 1
                elif model_margin < 0:
                    tracker["negative_modelled_margin"] += 1
                else:
                    tracker["zero_modelled_margin"] += 1
                if direction == "positive" and model_margin <= 0:
                    tracker["price_up_erased_by_friction"] += 1
                if bps == 0:
                    audit_row = {"issuer": code,
                                 "signal_completed_day": signal.isoformat(),
                                 "cost_example": {
                                     k: str(v) if isinstance(v, Decimal) else v
                                     for k, v in model.items()
                                 }}
            if len(sample) < 5 and audit_row is not None:
                sample.append(audit_row)
        if (directions["positive"], directions["negative"], directions["flat"]) != (
                expected_positive, expected_negative, expected_flat):
            return reject("REPORTED_PRICE_DIRECTIONS_MISMATCH")
        scenarios = []
        for bps in BPS:
            d = totals[bps]
            if (d["all_observed"] != d["one_lot_cash_cap_passed"] + d["one_lot_cash_cap_exceeded"]
                    or d["one_lot_cash_cap_passed"] != d["positive_modelled_margin"] +
                    d["negative_modelled_margin"] + d["zero_modelled_margin"]):
                return reject("SCENARIO_ACCOUNTING_MISMATCH")
            scenarios.append({
                "assumed_slippage_bps_each_side": bps,
                "assumed_slippage_is_observed": False,
                "observed_price_pairs": d["all_observed"],
                "one_lot_proxy_within_cash_cap": d["one_lot_cash_cap_passed"],
                "one_lot_proxy_exceeds_cash_cap": d["one_lot_cash_cap_exceeded"],
                "price_up_pairs_within_cash_cap": d["observed_price_up_affordable"],
                "modelled_positive_margin_pairs": d["positive_modelled_margin"],
                "modelled_negative_margin_pairs": d["negative_modelled_margin"],
                "modelled_zero_margin_pairs": d["zero_modelled_margin"],
                "price_up_but_friction_erases_margin": d["price_up_erased_by_friction"],
                "win_rate": None, "broker_trade_count": 0,
            })
        return dict(
            base, status="OBSERVED_VENDOR_PRICE_FRICTION_SCENARIOS_NOT_BACKTEST",
            archive_commit_sha=proxy["archive_commit_sha"],
            holdout_cutoff_inclusive=cutoff.isoformat(),
            verified_nonoverlap_events=total,
            observed_price_pairs=n,
            censored_events=censored,
            future_vendor_status_blocked=blocked,
            observed_positive_price_changes=expected_positive,
            observed_negative_price_changes=expected_negative,
            observed_flat_price_changes=expected_flat,
            lot_size_shares=100,
            research_cash_cap_cny="8000.00",
            unverified_max_plan_risk_cny="240.00",
            fee_assumptions={
                "per_side_commission_rate": str(COMMISSION),
                "commission_min_cny_each_side": "5.00",
                "sell_only_stamp_rate": str(STAMP_ON_SELL),
                "SH_per_side_transfer_rate": str(SH_TRANSFER),
                "SZ_extra_transfer_modelled": False,
                "fee_rounding": "each line to CNY cents, HALF_UP",
                "contract_status": "SCENARIO_NOT_ACCOUNT_STATEMENT",
                "references": [
                    "https://www.ctsec.com/company/detail/9316859",
                    "https://one.sse.com.cn/onething/gptz/",
                ],
            },
            scenarios=scenarios,
            sample_price_pair_cost_checks=sample,
            limitations=[
                "PRICE_PROXY_AFTER_HYPOTHETICAL_COSTS_NOT_TRADE_PNL",
                "OBSERVED_NEXT_OPEN_AND_THIRD_CLOSE_NOT_GUARANTEED_FILLS",
                "ONE_LOT_CAP_IS_NOT_LIQUIDITY_OR_RISK_AUTHORIZATION",
                "NO_PRETRADE_STOP_OR_2_TO_1_REWARD_RISK_CHECK",
                "CENSORED_OR_UNTRADABLE_EVENTS_NOT_ASSIGNED_ZERO",
                "REPEATED_ISSUER_EVENTS_AND_SURVIVORSHIP_NOT_VALIDATED",
                "HISTORICAL_PIT_ST_SECTOR_AND_COMPANY_ACTIONS_NOT_CERTIFIED",
            ],
        )
    except (KeyError, ValueError, TypeError, InvalidOperation, ArithmeticError,
            OverflowError):
        return reject("MALFORMED_OR_INCONSISTENT_PRICE_PROXY")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    try:
        payload = json.loads(Path(a.input).read_text())
    except (OSError, ValueError, UnicodeError):
        payload = None
    result = audit(payload)
    destination = Path(a.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result.get(key) for key in (
        "status", "observed_price_pairs", "scenarios", "trade_gate"
    )}, ensure_ascii=False))
    if result["status"] == "REJECTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
