"""As-of signal-weekday preflight for frozen Friday-exit research (NO TRADES).

Unlike a retrospective first-Friday OHLC check, this consumes *only* the
date a completed MA20 signal was knowable after close. It never reads future
vendor open, high, low, close, later row date, intrabar touch or future
tradestatus to select a candidate. Because an independently authenticated
exchange calendar available AT signal-time is still missing, all results
fail closed; next-weekday estimates are illustrations, not entry dates.

Do not use this output as an entry/portfolio filter until a separately
validated prepublished historical calendar and issuer PIT replay exist.
"""
import argparse
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

PHASE = "P4_ASOF_SIGNAL_WEEKDAY_FRIDAY_RESEARCH_PRECHECK"
SRC = "P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES"
SHA = re.compile(r"[a-f0-9]{40}\Z")
CODE = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
CATEGORIES = (
    "MON_OR_FRI_SIGNAL_CONDITIONAL_DATE_WINDOW_ONLY",
    "TUE_OR_WED_SIGNAL_POTENTIAL_EARLY_FRIDAY_CONFLICT",
    "THU_SIGNAL_POTENTIAL_FRIDAY_ENTRY_TPLUS1_CONFLICT",
)
MAX_ROWS = 50000


def signal_date(text):
    if not isinstance(text, str):
        raise ValueError("signal date missing")
    day = date.fromisoformat(text)
    if day.isoformat() != text or day.weekday() >= 5:
        raise ValueError("invalid canonical weekday signal date")
    return day


def classify_signal_day(day):
    """Always provisional: weekday arithmetic ignores exchange holidays."""
    wd = day.weekday()
    if wd in (0, 4):
        return CATEGORIES[0]
    if wd in (1, 2):
        return CATEGORIES[1]
    if wd == 3:
        return CATEGORIES[2]
    raise ValueError("weekend is not a completed session")


def calendar_diagnostic(signal, calendar):
    """Research-only deterministic session-calendar evaluation.

    An untrusted list of dates CANNOT authenticate the calendar's first
    publication or prove that it existed as of the original signal close.
    Output is never a buy signal. It tests policy arithmetic with scheduled
    exchange dates *only*, no future price or volume fields.
    """
    day = signal_date(signal)
    base = {
        "calendar_asof_authenticity_certified": False,
        "historical_issuer_pit_certified": False,
        "trade_authorized": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }
    if calendar is None:
        return dict(base, status="BLOCK_MISSING_PREPUBLISHED_EXCHANGE_CALENDAR")
    if (not isinstance(calendar, list) or not 2 <= len(calendar) <= 400
            or any(not isinstance(x, str) for x in calendar)):
        return dict(base, status="BLOCK_MALFORMED_CALENDAR_RESEARCH_INPUT")
    try:
        sessions = [signal_date(x) for x in calendar]
    except ValueError:
        return dict(base, status="BLOCK_MALFORMED_CALENDAR_RESEARCH_INPUT")
    if sessions != sorted(set(sessions)):
        return dict(base, status="BLOCK_DUPLICATED_OR_UNSORTED_CALENDAR")
    if day not in sessions:
        return dict(base, status="BLOCK_SIGNAL_DAY_ABSENT_FROM_CALENDAR")
    future = [x for x in sessions if x > day]
    if not future:
        return dict(base, status="BLOCK_NO_NEXT_SESSION_IN_CALENDAR")
    entry = future[0]
    if (entry - day).days > 14:
        return dict(base, status="BLOCK_CALENDAR_GAP_LONGER_THAN_14_DAYS")
    if entry.weekday() == 4:
        return dict(base, status="RESEARCH_VETO_FRIDAY_ENTRY_TPLUS1",
                    hypothetical_next_session=entry.isoformat())
    # Within a calendar week, the last scheduled open day (possibly Thursday
    # on a Friday holiday) is the final opportunity before the weekend.
    year, week, _ = entry.isocalendar()
    same_week = [
        x for x in sessions if x >= entry and
        x.isocalendar()[:2] == (year, week)
    ]
    if not same_week:
        return dict(base, status="BLOCK_WEEKEND_EXIT_CALENDAR_INCOMPLETE")
    # The input may be truncated on a Wednesday/Thursday. Its last item
    # is not evidence that Thursday replaced Friday as the week's last
    # exchange session. Require at least one explicitly listed subsequent
    # week as a horizon boundary, even for a hypothetical holiday week.
    if not any(x.isocalendar()[:2] > (year,week) for x in sessions):
        return dict(base, status="BLOCK_CALENDAR_WEEK_END_UNOBSERVED",
                    hypothetical_next_session=entry.isoformat(),
                    calendar_terminal_date=sessions[-1].isoformat())
    last_weekday_session = same_week[-1]
    if (last_weekday_session - entry).days > 6:
        return dict(base, status="BLOCK_CALENDAR_WEEK_INCONSISTENT")
    # Count post-entry calendar sessions to week-end. Do not claim any fill
    # or that a historical open-day calendar was independently authenticated.
    post_entry = len(same_week)-1
    if post_entry < 3:
        label = "RESEARCH_VETO_EARLY_WEEKEND_BEFORE_3_SESSIONS"
    elif post_entry <= 5:
        label = "RESEARCH_DATE_ARITHMETIC_COMPATIBLE_UNAUTHENTICATED"
    else:
        label = "BLOCK_INCONSISTENT_FIVE_SESSION_WEEK"
    return dict(
        base, status=label, hypothetical_next_session=entry.isoformat(),
        hypothetical_week_end_exit_session=last_weekday_session.isoformat(),
        calendar_sessions_after_hypothetical_entry_before_weekend=post_entry,
        research_only_calendar_list_is_untrusted=True,
    )


def audit(proxy):
    base = {
        "phase": PHASE, "status": "REJECTED", "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
        "trade_authorized": False, "approved_entries": 0,
        "broker_fills_verified": 0, "strategy_returns_computed": False,
        "historical_PIT_verified": False, "historical_OOS_validated": False,
        "historical_calendar_asof_authenticated": False,
        "future_vendor_bars_used_in_entry_precheck": False,
        "preentry_executable_signal_generated": False,
    }

    def fail(reason):
        return dict(base, reason=reason)
    if (not isinstance(proxy, dict)
            or proxy.get("phase") != SRC
            or proxy.get("status") != "OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST"
            or not isinstance(proxy.get("archive_commit_sha"), str)
            or not SHA.fullmatch(proxy["archive_commit_sha"])
            or proxy.get("trade_gate") != "BLOCKED"
            or proxy.get("orders") != []
            or proxy.get("executable_candidates") != []
            or proxy.get("actionable_buy_signals") != []
            or proxy.get("historical_PIT_verified") is not False
            or proxy.get("historical_OOS_validated") is not False
            or proxy.get("strategy_backtest_certified") is not False
            or proxy.get("fills_assumed") != 0
            or proxy.get("trades_assumed") != 0):
        return fail("UNTRUSTED_OR_UNSAFE_RESEARCH_SOURCE")
    records = proxy.get("observed_price_pairs")
    count = proxy.get("observed_next_open_to_third_close")
    if (not isinstance(records, list) or type(count) is not int
            or not 0 <= count <= MAX_ROWS or len(records) != count):
        return fail("TRUNCATED_SOURCE_EVENT_SET")
    results = Counter()
    signal_weekdays = Counter()
    seen = set()
    try:
        for row in records:
            if not isinstance(row, dict):
                return fail("INVALID_SOURCE_EVENT")
            code = row.get("issuer")
            signal = row.get("signal_known_after_close_date")
            if (not isinstance(code, str) or not CODE.fullmatch(code)
                    or row.get("next_open_fill_assumed") is not False
                    or row.get("exit_close_fill_assumed") is not False
                    or row.get("T_plus_1_execution_verified") is not False
                    or row.get("trade_return") is not None):
                return fail("FORGED_ENTRY_OR_NON_MAINBOARD_SIGNAL")
            key = (code, signal)
            if key in seen:
                return fail("DUPLICATE_SIGNAL_FOR_ONE_ISSUER_DAY")
            seen.add(key)
            # Only this completed-signal date is permitted in decision
            # arithmetic. Ignore next_vendor_date, observed OHLC, Friday
            # future status, and all subsequent outcomes by construction.
            day = signal_date(signal)
            signal_weekdays[day.strftime("%A").upper()] += 1
            results[classify_signal_day(day)] += 1
    except (KeyError, TypeError, ValueError, OverflowError):
        return fail("NON_CANONICAL_SIGNAL_DATE")
    if sum(results.values()) != count or sum(signal_weekdays.values()) != count:
        return fail("UNRECONCILED_SIGNAL_DAY_CLASSIFICATIONS")
    return dict(
        base, status="ASOF_WEEKDAY_ONLY_NO_AUTHENTICATED_CALENDAR_NO_TRADES",
        archive_commit_sha=proxy["archive_commit_sha"],
        verified_mature_proxy_signals=count,
        signal_weekday_histogram=dict(sorted(signal_weekdays.items())),
        conditional_next_weekday_screen={
            category:results[category] for category in CATEGORIES},
        calendar_certificate_missing_for_all=count,
        first_publication_of_exchange_calendar_verified=0,
        entry_precheck_veto_is_not_an_exit_fill=True,
        limitations=[
            "NEXT_WEEKDAY_NOT_AUTHENTICATED_EXCHANGE_NEXT_TRADING_SESSION",
            "NO_PREPUBLISHED_HISTORICAL_CALENDAR_RECEIPT_AT_SIGNAL_TIME",
            "EX_POST_PRICE_AND_VENDOR_STATUS_NOT_INPUTS_TO_ENTRY_PRECHECK",
            "SIGNAL_DAY_ONLY_RESEARCH_CANNOT_AUTHORIZE_NEW_POSITION",
            "HOLIDAYS_MAY_CHANGE_ALL_CONDITIONAL_WEEKDAY_CLASSIFICATIONS",
            "FRIDAY_EXIT_REQUIRES_REAL_CALENDAR_AND_MARKET_FILLABILITY",
        ],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        result = audit(json.loads(Path(args.proxy).read_text()))
    except (OSError, ValueError, UnicodeError):
        result = audit(None)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({
        k:result.get(k) for k in (
            "status", "verified_mature_proxy_signals",
            "conditional_next_weekday_screen", "calendar_certificate_missing_for_all",
            "trade_gate")}, ensure_ascii=False))
    if result["status"] == "REJECTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
