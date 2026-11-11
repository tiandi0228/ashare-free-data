"""T+1-aware OHLC barrier *touch* audit, not a fill simulator or trade backtest.

Freeze a hypothetical 100-share gross -2% / +5% barrier around the next
vendor open. Risk/2:1 checks include modelled two-sided fees and a fixed 10-bp
per-side price friction scenario. The entry and exit prices are NOT fills.
Daily OHLC cannot establish intrabar order, price-limit queue priority, or a
same-day sale on T+1 instruments. Ambiguities remain explicit and non-tradable.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path

from collector.p4_independent_event_evidence import verify
from collector.p4_observed_fee_friction import CAPITAL, CENT, exposure

PHASE = "P4_TPLUS1_BARRIER_TOUCH_RESEARCH"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
BPS = 10
STOP_PCT = Decimal("0.02")
TARGET_PCT = Decimal("0.05")
MAX_RISK = CAPITAL * Decimal("0.03")


def positive(text):
    if not isinstance(text, str):
        raise ValueError("non-string price")
    x = Decimal(text)
    if not x.is_finite() or x <= 0:
        raise ValueError("bad price")
    return x


def barrier(entry):
    stop = (entry*(Decimal(1)-STOP_PCT)).quantize(CENT, rounding=ROUND_CEILING)
    target = (entry*(Decimal(1)+TARGET_PCT)).quantize(CENT, rounding=ROUND_CEILING)
    if not 0 < stop < entry < target:
        raise ValueError("tick-collapsed barrier")
    return stop, target


def bar_ohlc(row):
    if row.get("tradestatus") != "1":
        raise ValueError("vendor not tradable")
    o, h, l, c = (positive(row[k]) for k in ("open", "high", "low", "close"))
    if not (l <= o <= h and l <= c <= h):
        raise ValueError("contradictory bar")
    return o, h, l, c


def touches(bars, stop, target):
    """No exits inferred. Day 1 cannot be sold; later bars lack intrabar order."""
    entry_open, entry_high, entry_low, _ = bar_ohlc(bars[0])
    first_day_stop = entry_low <= stop
    first_day_target = entry_high >= target
    later_kind = "neither"
    later_day = None
    open_below = False
    open_above = False
    for i, row in enumerate(bars[1:], start=2):
        o, h, l, _ = bar_ohlc(row)
        stop_hit = l <= stop
        target_hit = h >= target
        if not (stop_hit or target_hit):
            continue
        later_day = i
        later_kind = ("both_unknown_order" if stop_hit and target_hit else
                      "stop_only" if stop_hit else "target_only")
        open_below = o < stop
        open_above = o > target
        break
    return first_day_stop, first_day_target, later_kind, later_day, open_below, open_above


def audit(root, manifest_file, proxy_file):
    base = {
        "phase": PHASE, "status": "REJECTED", "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
        "fills_assumed": 0, "trades_assumed": 0, "broker_trade_count": 0,
        "trade_returns_computed": False, "portfolio_pnl_computed": False,
        "strategy_backtest_certified": False, "historical_PIT_verified": False,
        "historical_OOS_validated": False, "risk_gate_verified": False,
        "trade_authorized": False,
    }
    def reject(reason):
        return dict(base, reason=reason)
    try:
        independently = verify(root, manifest_file)
        if independently.get("trade_gate") != "BLOCKED" or independently.get("orders") != []:
            return reject("UNSAFE_INDEPENDENT_ORIGINAL_REPLAY")
        manifest = json.loads(Path(manifest_file).read_text())
        proxy = json.loads(Path(proxy_file).read_text())
        sha = manifest.get("archive_commit_sha")
        if (not isinstance(sha, str) or not COMMIT.fullmatch(sha)
                or proxy.get("archive_commit_sha") != sha
                or proxy.get("phase") != "P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES"
                or proxy.get("status") != "OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST"
                or proxy.get("trade_gate") != "BLOCKED" or proxy.get("orders") != []
                or proxy.get("executable_candidates") != []
                or proxy.get("actionable_buy_signals") != []
                or proxy.get("fills_assumed") != 0 or proxy.get("trades_assumed") != 0
                or proxy.get("historical_PIT_verified") is not False
                or proxy.get("historical_OOS_validated") is not False
                or proxy.get("strategy_backtest_certified") is not False
                or proxy.get("holdout_cutoff_inclusive") != manifest.get("cutoff_inclusive")):
            return reject("UNSAFE_OR_MISMATCHED_PRICE_PROXY")
        events = manifest["nonoverlapping_event_evidence"]
        if (not isinstance(events, list)
                or independently.get("independently_verified_events") != len(events)
                or proxy.get("verified_nonoverlap_events") != len(events)):
            return reject("TRUNCATED_OR_MISMATCHED_EVENT_MANIFEST")
        pairs = proxy.get("observed_price_pairs")
        if (not isinstance(pairs, list) or len(pairs) > 50000
                or type(proxy.get("observed_next_open_to_third_close")) is not int
                or len(pairs) != proxy["observed_next_open_to_third_close"]
                or independently.get("independently_verified_forward_ready") != len(pairs)):
            return reject("UNRECONCILED_MATURE_EVENT_PAIRS")
        censored = proxy.get("censored_events")
        status_blocked = proxy.get("future_vendor_status_blocked")
        if (type(censored) is not int or type(status_blocked) is not int
                or censored < 0 or status_blocked < 0
                or len(pairs) + censored + status_blocked != len(events)):
            return reject("UNRECONCILED_CENSORED_OR_STATUS_BLOCKED_EVENTS")
        expected = {
            (e["issuer"], e["signal_completed_date"]): e
            for e in events if e["three_future_vendor_tradable"]
        }
        if len(expected) != len(pairs):
            return reject("DUPLICATED_OR_MISSING_MATURE_EVENTS")
        needed = {code for code, _ in expected}
        sources = {}
        for receipt in sorted(Path(root).glob("*/shard_*/quality.json")):
            raw_receipt = json.loads(receipt.read_text())
            for item in raw_receipt["results"]:
                code = item["code"]
                if code not in needed:
                    continue
                path = receipt.parent/(code.replace(".", "_")+".csv")
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                if digest != item["sha256"]:
                    return reject("ARCHIVED_ORIGINAL_SHA_MISMATCH")
                if code in sources:
                    if sources[code][0] != digest:
                        return reject("CONFLICTING_ARCHIVED_CSV")
                    continue
                sources[code] = (
                    digest, list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
                )
        counts = Counter()
        first_day = Counter()
        later = Counter()
        plan = Counter()
        samples = []
        seen = set()
        for pair in pairs:
            code, signal = pair["issuer"], pair["signal_known_after_close_date"]
            if not isinstance(code, str) or not ISSUER.fullmatch(code):
                return reject("INVALID_MAINBOARD_ISSUER")
            key = code, signal
            if key in seen or key not in expected or code not in sources:
                return reject("DUPLICATE_OR_UNPINNED_EVENT")
            seen.add(key)
            event = expected[key]
            digest, rows = sources[code]
            # A valid file hash does not prove its rows belong to this issuer.
            # Reject a cross-issuer CSV even if every surrounding SHA is repinned.
            if not rows or any(row.get("code") != code for row in rows):
                return reject("SOURCE_CSV_ISSUER_MISMATCH")
            if (digest != event["source_csv_sha256"]
                    or pair.get("original_csv_sha256") != digest
                    or pair.get("next_open_fill_assumed") is not False
                    or pair.get("exit_close_fill_assumed") is not False
                    or pair.get("T_plus_1_execution_verified") is not False
                    or pair.get("trade_return") is not None):
                return reject("FORGED_EXECUTION_OR_ORIGINAL_SOURCE")
            positions = [i for i, r in enumerate(rows) if r["date"] == signal]
            if len(positions) != 1:
                return reject("AMBIGUOUS_SIGNAL_POSITION")
            i = positions[0]
            future = rows[i+1:i+4]
            if (len(future) != 3 or
                    [r["date"] for r in future] != event["three_future_observed_dates"] or
                    future[0]["date"] != pair.get("next_vendor_date") or
                    future[2]["date"] != pair.get("third_vendor_date")):
                return reject("FUTURE_DAY_RECONCILIATION_FAILED")
            first_open = positive(pair["next_vendor_open"])
            third_close = positive(pair["third_vendor_close"])
            if (first_open != positive(future[0]["open"]) or
                    third_close != positive(future[2]["close"])):
                return reject("PROXY_PRICE_NOT_IN_ARCHIVED_OHLC")
            stop, target = barrier(first_open)
            entry_day_stop, entry_day_target, kind, day_index, gap_below, gap_above = (
                touches(future, stop, target))
            counts["observed_pairs"] += 1
            first_day["stop_touched_sell_not_allowed"] += int(entry_day_stop)
            first_day["target_touched_sell_not_allowed"] += int(entry_day_target)
            first_day["both_touched_sell_not_allowed"] += int(
                entry_day_stop and entry_day_target)
            later[kind] += 1
            later["gap_open_below_stop"] += int(gap_below)
            later["gap_open_above_target"] += int(gap_above)
            if day_index is not None:
                later["first_touch_second_vendor_day"] += int(day_index == 2)
                later["first_touch_third_vendor_day"] += int(day_index == 3)
            entry = exposure(first_open, third_close, code, BPS)
            if not entry["affordable_one_lot_proxy"]:
                plan["one_lot_exceeds_cash_cap"] += 1
                continue
            plan["one_lot_cash_cap_passed"] += 1
            stop_cost = exposure(first_open, stop, code, BPS)
            target_cost = exposure(first_open, target, code, BPS)
            risk = -stop_cost["modelled_margin_after_friction_cny"]
            reward = target_cost["modelled_margin_after_friction_cny"]
            if risk <= 0:
                plan["unusable_nonpositive_proxy_risk"] += 1
                continue
            if risk <= MAX_RISK:
                plan["modelled_stop_risk_within_3pct_cash_cap"] += 1
            if reward >= 2*risk:
                plan["modelled_reward_at_least_2x_stop_risk"] += 1
            if risk <= MAX_RISK and reward >= 2*risk:
                plan["both_theoretical_barrier_thresholds_met"] += 1
            if len(samples) < 5:
                samples.append({
                    "issuer": code, "signal_completed_day": signal,
                    "next_vendor_entry_open": str(first_open),
                    "stop_gross_2pct_ceil_tick": str(stop),
                    "target_gross_5pct_ceil_tick": str(target),
                    "modelled_stop_loss_including_friction_cny": str(risk),
                    "modelled_target_margin_including_friction_cny": str(reward),
                    "entry_day_stop_touched_but_sale_ineligible": entry_day_stop,
                    "later_first_touch_type": kind,
                    "later_first_touch_day_index": day_index,
                    "actual_fill": False,
                })
        if len(seen) != len(expected):
            return reject("MISSING_MATURE_EVENT_PAIRS")
        if (sum(later[k] for k in ("stop_only", "target_only",
                                   "both_unknown_order", "neither")) != len(pairs)
                or plan["one_lot_exceeds_cash_cap"] +
                plan["one_lot_cash_cap_passed"] != len(pairs)):
            return reject("BARRIER_ACCOUNTING_MISMATCH")
        return dict(base,
            status="TPLUS1_BARRIER_TOUCHES_NOT_EXECUTABLE_BACKTEST",
            archive_commit_sha=sha,
            source_verified_mature_price_pairs=len(pairs),
            censored_not_extrapolated=proxy["censored_events"],
            vendor_status_blocked_not_extrapolated=proxy["future_vendor_status_blocked"],
            hypothetical_barriers={
                "entry": "first vendor open after completed signal, not a fill",
                "stop_percent_gross": "2.00",
                "target_percent_gross": "5.00",
                "stop_tick_rounding": "CEILING_TO_0.01",
                "target_tick_rounding": "CEILING_TO_0.01",
                "assumed_slippage_bps_per_side": BPS,
                "slippage_observed": False,
                "minimum_100_share_lot": 100,
                "research_cash_limit_cny": str(CAPITAL),
                "research_risk_cap_cny": str(MAX_RISK),
                "T_plus_1_rule": "entry day is ineligible for selling",
            },
            entry_day_touches=dict(first_day),
            first_sell_eligible_days_touches={
                k: later[k] for k in ("stop_only", "target_only",
                    "both_unknown_order", "neither",
                    "gap_open_below_stop", "gap_open_above_target",
                    "first_touch_second_vendor_day", "first_touch_third_vendor_day")
            },
            theoretical_friction_plan_checks={
                k: plan[k] for k in ("one_lot_cash_cap_passed",
                    "one_lot_exceeds_cash_cap",
                    "unusable_nonpositive_proxy_risk",
                    "modelled_stop_risk_within_3pct_cash_cap",
                    "modelled_reward_at_least_2x_stop_risk",
                    "both_theoretical_barrier_thresholds_met")
            },
            sample_audits=samples,
            limitations=[
                "FIRST_VENDOR_OPEN_NOT_FILLED_ENTRY",
                "T_PLUS_ONE_MAKES_ENTRY_DAY_STOP_UNEXECUTABLE",
                "BOTH_BARRIERS_ON_SAME_DAY_HAVE_UNKNOWN_ORDER",
                "GAP_OPEN_PRICE_NOT_GUARANTEED_EXECUTION",
                "SELL_PRICE_LIMIT_OR_QUEUE_NOT_AUTHENTICATED",
                "FROZEN_BARRIERS_NOT_PREDICTIVE_STRATEGY_OR_REAL_STOPS",
                "HISTORICAL_PIT_ST_AND_CORPORATE_ACTIONS_UNCERTIFIED",
                "NO_3_TO_5_DAY_OOS_STRATEGY_OR_LIVE_QUOTE_CERTIFICATION",
            ])
    except (OSError, ValueError, KeyError, TypeError, IndexError,
            InvalidOperation, ArithmeticError, OverflowError):
        return reject("SOURCE_OR_PRICE_BAR_INTEGRITY_ERROR")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--proxy", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = audit(args.root, args.manifest, args.proxy)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({
        k: result.get(k) for k in (
            "status", "source_verified_mature_price_pairs",
            "entry_day_touches", "first_sell_eligible_days_touches",
            "theoretical_friction_plan_checks", "trade_gate"
        )}, ensure_ascii=False))
    if result["status"] == "REJECTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
