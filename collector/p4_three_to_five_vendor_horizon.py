"""P4 3-5 observed vendor-session horizon and Friday rule research (NO TRADES).

The existing first next vendor OPEN and third later CLOSE are *not* a
3-to-5-session strategy exit, an authenticated exchange calendar, a fill, or
historical PIT. Inspect additional SHA-linked archived bars to quantify
which 3/4/5-session *after hypothetical entry* observations exist, whether
vendor tradestatus blocks those windows, and how a mandatory Friday exit
conflicts with minimum three-session holding / entry-Friday T+1.

No prices are used to calculate strategy returns or hypothetical fills.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from collector.p4_independent_event_evidence import verify

PHASE = "P4_THREE_TO_FIVE_VENDOR_SESSION_COVERAGE_RESEARCH"
ARCHIVE_SHA = re.compile(r"[0-9a-f]{40}\Z")
CSV_SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
HORIZONS = (3, 4, 5)
MAX_EVENTS = 50000


def _ohlc_volume_queue_boundary(row):
    """Historical *daily* vendor bar cannot certify a bid/ask fill or price limit.

    Single-price bars and zero-volume vendor observations diagnose plausible
    unfillable/queued orders. Variable historical ST/price-limit rules and
    intraday auction queue state are absent and NEVER guessed from OHLC.
    """
    if row.get("tradestatus") != "1":
        return "VENDOR_STATUS_NOT_TRADABLE"
    try:
        texts = [row.get(k) for k in ("open","high","low","close","volume")]
        if any(not isinstance(t,str) or not t for t in texts):
            raise ValueError("non-string or empty vendor OHLC/volume")
        o,h,l,c,v = map(Decimal, texts)
        if any(not x.is_finite() for x in (o,h,l,c,v)):
            raise ValueError("nonfinite vendor OHLC or volume")
        if not (0<l<=o<=h and l<=c<=h and v>=0):
            raise ValueError("invalid vendor OHLC or volume")
    except (InvalidOperation, ValueError, ArithmeticError):
        raise ValueError("unsafe vendor OHLC/volume proof")
    if v == 0:
        return "VENDOR_ZERO_VOLUME_NO_EXECUTED_TRADE_PRINTS"
    if o==h==l==c:
        return "ONE_PRICE_BAR_AUCTION_QUEUE_UNVERIFIED"
    return "VENDOR_DAILY_RANGE_PRESENT_NO_ORDER_BOOK_OR_FILL_PROOF"


def _day(raw):
    if not isinstance(raw, str):
        raise ValueError("missing dated vendor row")
    result = date.fromisoformat(raw)
    if result.isoformat() != raw or result.weekday() >= 5:
        raise ValueError("bad vendor observation date")
    return result


def audit(root, manifest_path, proxy_path):
    base = {
        "phase": PHASE, "status": "REJECTED", "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
        "fills_assumed": 0, "broker_fills_confirmed": 0,
        "realtime_quote_verified": False, "trading_calendar_certified": False,
        "historical_PIT_verified": False, "historical_OOS_validated": False,
        "strategy_backtest_certified": False, "trade_authorized": False,
        "portfolio_pnl_computed": False, "strategy_returns_computed": False,
    }
    def reject(reason):
        return dict(base, reason=reason)

    try:
        source = json.loads(Path(manifest_path).read_text())
        proxy = json.loads(Path(proxy_path).read_text())
        sha = source.get("archive_commit_sha")
        if (not isinstance(sha, str) or not ARCHIVE_SHA.fullmatch(sha)
                or proxy.get("archive_commit_sha") != sha
                or source.get("phase") != "P4_REAL_VENDOR_MA20_FORWARD_OBSERVATION"
                or source.get("trade_gate") != "BLOCKED"
                or source.get("orders") != []
                or source.get("executable_candidates") != []
                or source.get("historical_PIT_verified") is not False
                or source.get("historical_OOS_validated") is not False
                or proxy.get("phase") != "P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES"
                or proxy.get("status") != "OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST"
                or proxy.get("trade_gate") != "BLOCKED"
                or proxy.get("orders") != [] or proxy.get("executable_candidates") != []
                or proxy.get("actionable_buy_signals") != []
                or proxy.get("fills_assumed") != 0 or proxy.get("trades_assumed") != 0
                or proxy.get("historical_PIT_verified") is not False
                or proxy.get("historical_OOS_validated") is not False
                or proxy.get("strategy_backtest_certified") is not False
                or proxy.get("holdout_cutoff_inclusive") != source.get("cutoff_inclusive")):
            return reject("UNSAFE_OR_UNRELATED_ORIGINAL_PRICE_SOURCES")
        independent = verify(root, manifest_path)
        if (independent.get("trade_gate") != "BLOCKED"
                or independent.get("orders") != []
                or independent.get("independently_verified_events") !=
                source.get("nonoverlapping_three_observation_crossing_events")
                or independent.get("independently_verified_forward_ready") !=
                proxy.get("observed_next_open_to_third_close")):
            return reject("INCOMPLETE_OR_UNVERIFIED_ORIGINAL_EVENT_REPLAY")
        events = source.get("nonoverlapping_event_evidence")
        pairs = proxy.get("observed_price_pairs")
        if (not isinstance(events, list) or not isinstance(pairs, list)
                or len(events) > MAX_EVENTS or len(pairs) > MAX_EVENTS
                or type(proxy.get("observed_next_open_to_third_close")) is not int
                or len(pairs) != proxy["observed_next_open_to_third_close"]
                or type(proxy.get("verified_nonoverlap_events")) is not int
                or len(events) != proxy["verified_nonoverlap_events"]):
            return reject("TRUNCATED_OR_UNBOUNDED_EVENT_LIST")
        # Every modeled entry must correspond to exactly one previously
        # independently verified three-original-row vendor-ready event.
        expected = {
            (e["issuer"], e["signal_completed_date"]): e for e in events
            if e["three_future_vendor_tradable"] is True
        }
        if len(expected) != len(pairs):
            return reject("PRICE_PROXY_MATURE_EVENTS_NOT_RECONCILED")
        need = {x["issuer"] for x in events}
        originals = {}
        for receipt in sorted(Path(root).glob("*/shard_*/quality.json")):
            info = json.loads(receipt.read_text())
            for item in info["results"]:
                code = item["code"]
                if code not in need:
                    continue
                if (not isinstance(code, str) or not ISSUER.fullmatch(code)
                        or not isinstance(item.get("sha256"), str)
                        or not CSV_SHA.fullmatch(item["sha256"])):
                    return reject("INVALID_PRICE_ORIGINAL_RECEIPT")
                raw = (receipt.parent/(code.replace(".", "_")+".csv")).read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                if digest != item["sha256"]:
                    return reject("PRICE_ORIGINAL_SHA_CHANGED")
                if code in originals:
                    if originals[code][0] != digest:
                        return reject("CONFLICTING_VENDOR_ORIGINAL_SHA")
                    continue
                rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
                dates = [_day(r["date"]) for r in rows]
                if dates != sorted(set(dates)):
                    return reject("DUPLICATE_OR_UNORDERED_VENDOR_DATES")
                originals[code] = digest, rows
        seen = set()
        horizon_counts = {h: Counter() for h in HORIZONS}
        friday = Counter()
        friday_compatibility = Counter()
        entry_execution_boundary = Counter()
        friday_exit_execution_boundary = Counter()
        samples = []
        for pair in pairs:
            if not isinstance(pair, dict):
                return reject("INVALID_PRICE_PROXY_ROW")
            code = pair.get("issuer")
            signal = pair.get("signal_known_after_close_date")
            key = (code, signal)
            if (key in seen or key not in expected or code not in originals
                    or pair.get("next_open_fill_assumed") is not False
                    or pair.get("exit_close_fill_assumed") is not False
                    or pair.get("T_plus_1_execution_verified") is not False
                    or pair.get("trade_return") is not None):
                return reject("FORGED_ENTRY_OR_DUPLICATE_MATURE_EVENT")
            seen.add(key)
            orig_sha, rows = originals[code]
            event = expected[key]
            if (orig_sha != event["source_csv_sha256"]
                    or pair.get("original_csv_sha256") != orig_sha):
                return reject("SOURCE_SHA_OR_EVENT_IDENTITY_MISMATCH")
            positions = [i for i, row in enumerate(rows) if row["date"] == signal]
            if len(positions) != 1:
                return reject("AMBIGUOUS_SIGNAL_DATE")
            i = positions[0]
            first_three = rows[i+1:i+4]
            if (len(first_three) != 3
                    or any(row["tradestatus"] != "1" for row in first_three)
                    or [row["date"] for row in first_three] !=
                        event["three_future_observed_dates"]
                    or first_three[0]["date"] != pair.get("next_vendor_date")
                    or first_three[2]["date"] != pair.get("third_vendor_date")):
                return reject("FIRST_THREE_VENDOR_ROWS_CHANGED")
            # Cross-check prices only as provenance; NEVER compute trade returns.
            if (Decimal(first_three[0]["open"]) !=
                    Decimal(pair.get("next_vendor_open"))
                    or Decimal(first_three[2]["close"]) !=
                    Decimal(pair.get("third_vendor_close"))):
                return reject("SOURCE_PRICE_PROVENANCE_MISMATCH")
            entry_day = _day(first_three[0]["date"])
            entry_book_kind=_ohlc_volume_queue_boundary(first_three[0])
            if entry_book_kind=="VENDOR_STATUS_NOT_TRADABLE":
                return reject("HYPOTHETICAL_ENTRY_DAY_VENDOR_STATUS_CONTRADICTS_PROXY")
            entry_execution_boundary[entry_book_kind]+=1
            # Vendor rows after SIGNAL, from entry day through 5 sessions
            # *following* hypothetical entry; six vendor rows in total.
            window = rows[i+1:i+7]
            observation = {}
            for h in HORIZONS:
                available = window[:h+1]
                if len(available) < h+1:
                    category = "CENSORED_ARCHIVE_END"
                    day = None
                elif any(r["tradestatus"] != "1" for r in available):
                    category = "VENDOR_STATUS_BLOCKED"
                    day = None
                else:
                    category = "VENDOR_OBSERVATIONS_AVAILABLE_NOT_EXECUTION"
                    day = available[h]["date"]
                horizon_counts[h][category] += 1
                observation[str(h)] = day
            # Friday exit is a separate frozen rule. The first Friday
            # *after* the entry's own date may require exit BEFORE 3 sessions.
            first_friday_index = None
            if entry_day.weekday() == 4:
                friday["ENTRY_FRIDAY_TPLUS1_CANNOT_CLEAR_SAME_FRIDAY"] += 1
                friday_kind = "ENTRY_FRIDAY_TPLUS1_CANNOT_CLEAR_SAME_FRIDAY"
            else:
                first_friday_index = next(
                    (position for position, item in enumerate(window[1:], start=1)
                     if _day(item["date"]).weekday() == 4), None)
                if first_friday_index is None:
                    friday_kind = "FIRST_FRIDAY_NOT_OBSERVED_IN_BOUNDED_WINDOW"
                elif first_friday_index < 3:
                    friday_kind = "FRIDAY_BEFORE_MINIMUM_THREE_VENDOR_SESSIONS"
                else:
                    friday_kind = "FRIDAY_AT_THREE_TO_FIVE_VENDOR_SESSIONS"
                friday[friday_kind] += 1
            # Conservative *ex-post* consistency audit only. The future
            # vendor status and future existence of Friday rows are NOT
            # knowable when an entry signal is formed. No trade permission
            # or look-ahead strategy signal may be inferred from this count.
            if friday_kind == "ENTRY_FRIDAY_TPLUS1_CANNOT_CLEAR_SAME_FRIDAY":
                compatibility_kind = "NO_GO_ENTRY_FRIDAY_TPLUS1"
            elif friday_kind == "FRIDAY_BEFORE_MINIMUM_THREE_VENDOR_SESSIONS":
                compatibility_kind = "NO_GO_MINIMUM_HOLD_VS_FRIDAY"
            elif friday_kind == "FIRST_FRIDAY_NOT_OBSERVED_IN_BOUNDED_WINDOW":
                compatibility_kind = "UNKNOWN_FIRST_FRIDAY_NOT_IN_ARCHIVE_WINDOW"
            elif first_friday_index is None or not 3 <= first_friday_index <= 5:
                return reject("FRIDAY_POSITION_CONTRADICTS_HOLDING_POLICY")
            elif any(r["tradestatus"] != "1"
                     for r in window[:first_friday_index+1]):
                compatibility_kind = "UNKNOWN_VENDOR_STATUS_BEFORE_FRIDAY"
            else:
                compatibility_kind = "OBSERVED_FRIDAY_WINDOW_ONLY_NOT_TRADABLE"
            friday_compatibility[compatibility_kind] += 1
            if friday_kind=="ENTRY_FRIDAY_TPLUS1_CANNOT_CLEAR_SAME_FRIDAY":
                friday_book_kind="ENTRY_FRIDAY_TPLUS1_SAME_DAY_EXIT_FORBIDDEN"
            elif friday_kind=="FRIDAY_BEFORE_MINIMUM_THREE_VENDOR_SESSIONS":
                friday_book_kind="FRIDAY_EXIT_BEFORE_FROZEN_MINIMUM_HOLD"
            elif first_friday_index is None:
                friday_book_kind="FRIDAY_EXIT_SOURCE_CENSORED_UNKNOWN"
            elif first_friday_index>=len(window):
                return reject("FRIDAY_INDEX_OUTSIDE_VENDOR_WINDOW")
            else:
                friday_book_kind=_ohlc_volume_queue_boundary(
                    window[first_friday_index])
            friday_exit_execution_boundary[friday_book_kind]+=1
            if len(samples) < 6:
                samples.append({
                    "issuer": code, "signal_completed_day": signal,
                    "hypothetical_entry_vendor_day_not_fill": entry_day.isoformat(),
                    "vendor_day_after_entry_3_4_5": observation,
                    "friday_constraint": friday_kind,
                    "friday_minimum_holding_compatibility": compatibility_kind,
                    "entry_daily_ohlc_liquidity_caution": entry_book_kind,
                    "first_friday_exit_ohlc_liquidity_caution": friday_book_kind,
                    "confirmed_buy_order_book_queue": False,
                    "confirmed_sell_order_book_queue": False,
                    "verified_price_limit_band": False,
                    "first_friday_vendor_date_unverified": (
                        window[first_friday_index]["date"]
                        if first_friday_index is not None else None),
                    "confirmed_entry_fill": False, "confirmed_exit_fill": False,
                })
        if len(seen) != len(expected):
            return reject("MATURE_PRICE_PAIR_SET_INCOMPLETE")
        for h in HORIZONS:
            if sum(horizon_counts[h].values()) != len(pairs):
                return reject("HORIZON_COVERAGE_ACCOUNTING_FAILED")
        if sum(friday.values()) != len(pairs):
            return reject("FRIDAY_COVERAGE_ACCOUNTING_FAILED")
        if sum(friday_compatibility.values()) != len(pairs):
            return reject("FRIDAY_COMPATIBILITY_ACCOUNTING_FAILED")
        if (sum(entry_execution_boundary.values()) != len(pairs)
                or sum(friday_exit_execution_boundary.values()) != len(pairs)):
            return reject("VENDOR_DAILY_OHLC_LIQUIDITY_COVERAGE_MISMATCH")
        if (friday_compatibility["NO_GO_ENTRY_FRIDAY_TPLUS1"] !=
                friday["ENTRY_FRIDAY_TPLUS1_CANNOT_CLEAR_SAME_FRIDAY"]
                or friday_compatibility["NO_GO_MINIMUM_HOLD_VS_FRIDAY"] !=
                friday["FRIDAY_BEFORE_MINIMUM_THREE_VENDOR_SESSIONS"]
                or friday_compatibility[
                    "OBSERVED_FRIDAY_WINDOW_ONLY_NOT_TRADABLE"] +
                    friday_compatibility["UNKNOWN_VENDOR_STATUS_BEFORE_FRIDAY"] !=
                    friday["FRIDAY_AT_THREE_TO_FIVE_VENDOR_SESSIONS"]):
            return reject("FRIDAY_POLICY_CAUSAL_COUNT_MISMATCH")
        return dict(
            base, status="THREE_TO_FIVE_VENDOR_COVERAGE_ONLY_NO_BACKTEST",
            archive_commit_sha=sha,
            verified_original_ma20_crossing_events=len(events),
            hypothetical_entry_price_pairs=len(pairs),
            horizon_sessions_after_hypothetical_entry={
                str(h): {
                    "vendor_observations_available_not_fills":
                        horizon_counts[h]["VENDOR_OBSERVATIONS_AVAILABLE_NOT_EXECUTION"],
                    "insufficient_original_rows_censored":
                        horizon_counts[h]["CENSORED_ARCHIVE_END"],
                    "vendor_status_blocked":
                        horizon_counts[h]["VENDOR_STATUS_BLOCKED"],
                } for h in HORIZONS},
            friday_mandatory_exit_conflicts=dict(sorted(friday.items())),
            entry_daily_ohlc_queue_ambiguity=dict(sorted(
                entry_execution_boundary.items())),
            friday_exit_daily_ohlc_queue_ambiguity=dict(sorted(
                friday_exit_execution_boundary.items())),
            historical_issuer_st_price_limit_band_verified=False,
            continuous_order_book_queue_replayed=False,
            confirmed_entry_fill_count=0,
            confirmed_friday_exit_fill_count=0,
            entry_daily_ohlc_not_an_executable_buy_quote=True,
            friday_and_minimum_holding_compatibility_research=dict(
                sorted(friday_compatibility.items())),
            pre_entry_friday_policy_trade_permission_certified=False,
            lookahead_data_used_for_entry_screening=False,
            prospective_friday_calendar_rule_frozen=False,
            historical_exchange_calendar_complete=False,
            official_historical_status_intervals_complete=False,
            samples=samples,
            limitations=[
                "AFTER_ENTRY_THREE_SESSIONS_NEEDS_FOUR_ROWS_AFTER_SIGNAL",
                "FIVE_SESSIONS_AFTER_ENTRY_NEEDS_SIX_ROWS_AFTER_SIGNAL",
                "VENDOR_ROWS_ARE_NOT_AN_AUTHENTICATED_EXCHANGE_CALENDAR",
                "FRIDAY_EXIT_OBLIGATION_DOES_NOT_PROVE_AN_ORDER_COULD_FILL",
                "ENTRY_FRIDAY_CANNOT_SAME_DAY_EXIT_UNDER_TPLUS1",
                "SUSPENDED_OR_CENSORED_SESSIONS_ARE_NOT_ZERO_RETURNS",
                "NO_HISTORICAL_PIT_TRADING_PERMISSION_OR_OOS_VALIDATION",
                "EX_POST_VENDOR_FRIDAY_STATUS_NOT_AVAILABLE_AT_DECISION_TIME",
                "OBSERVED_FRIDAY_WINDOW_NOT_EVIDENCE_OF_REAL_EXIT_FILL",
                "ZERO_DAILY_VOLUME_HAS_NO_EXECUTED_PRINT_NOT_A_BROKER_ORDER_LOG",
                "SINGLE_PRICE_BAR_CANNOT_PROVE_QUEUED_ORDER_PRIORITY_OR_EXECUTION",
                "DAILY_OHLC_HAS_NO_INTRADAY_TICKS_OR_ORDER_BOOK",
                "HISTORICAL_ST_PRICE_LIMIT_BAND_CANNOT_BE_INFERRED_FROM_OHLC",
                "STRICT_FRIDAY_MINIMUM_HOLDING_POLICY_STILL_RESEARCH_ONLY",
            ])
    except (OSError, KeyError, TypeError, ValueError,
            ArithmeticError, IndexError, UnicodeError):
        return reject("MISSING_OR_UNVERIFIABLE_VENDOR_SOURCE")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--proxy", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = audit(args.root, args.manifest, args.proxy)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({
        k: result.get(k) for k in ("status", "hypothetical_entry_price_pairs",
                                   "horizon_sessions_after_hypothetical_entry",
                                   "friday_mandatory_exit_conflicts", "trade_gate")
    }, ensure_ascii=False))
    if result["status"] == "REJECTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
