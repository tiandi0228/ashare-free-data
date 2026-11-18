"""Scoped 2026 holiday notice replay and synthetic P4 position risk checks."""
from datetime import date, timedelta

from collector.p4_position_notional_guard import check

SOURCES = {
    "SH": "https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml",
    "SZ": "https://www.szse.cn/www/disclosure/notice/general/t20260917_622911.html",
}
# Narrow contiguous slice of the September 17 notices. Outside this slice
# there is no evidence in this adapter. Not a certified historical calendar.
FIRST = date(2026, 9, 24)
LAST = date(2026, 10, 12)
NOTICES_AVAILABLE_DAY = date(2026, 9, 18)  # Day after publication; no assumed intraday time.
CLOSURES = ((date(2026, 9, 25), date(2026, 9, 27)),
            (date(2026, 10, 1), date(2026, 10, 7)))


def day(text):
    parsed = date.fromisoformat(text)
    if parsed.isoformat() != text:
        raise ValueError("use canonical calendar date")
    return parsed


def session_status(market, value, as_of):
    value, as_of = day(value), day(as_of)
    if market not in SOURCES:
        raise ValueError("unsupported market")
    if not FIRST <= value <= LAST or as_of < NOTICES_AVAILABLE_DAY:
        return "UNKNOWN"
    if value.weekday() >= 5 or any(first <= value <= last for first, last in CLOSURES):
        return "SCHEDULED_CLOSED"
    return "SCHEDULED_OPEN"


def replay(*, entry_day, exit_day, as_of, scenario):
    risk = check(scenario)
    market = risk["market"]
    entry, end = day(entry_day), day(exit_day)
    first = session_status(market, entry_day, as_of)
    last = session_status(market, exit_day, as_of)
    reasons = []
    elapsed = None
    if "UNKNOWN" in (first, last):
        reasons.append("CALENDAR_SCOPE_UNKNOWN")
    elif first != "SCHEDULED_OPEN" or last != "SCHEDULED_OPEN":
        reasons.append("ENTRY_OR_EXIT_SCHEDULED_CLOSED")
    elif end <= entry:
        reasons.append("TPLUS1_NOT_MET")
    else:
        elapsed = sum(
            session_status(market, (entry + timedelta(days=i)).isoformat(), as_of)
            == "SCHEDULED_OPEN" for i in range(1, (end - entry).days + 1)
        )
    if not risk["within_position_three_percent_stop_budget"]:
        reasons.append("POSITION_NET_STOP_BUDGET_EXCEEDED")
    if not risk["within_cash_budget"]:
        reasons.append("CASH_BUDGET_EXCEEDED")
    return {
        "status": "SCOPED_NOTICE_AND_SYNTHETIC_RISK_REPLAY_ONLY",
        "calendar_source": SOURCES[market], "entry_status": first, "exit_status": last,
        "scheduled_sessions_elapsed": elapsed, "blocking_reasons": reasons,
        "synthetic_checks_passed": not reasons, "risk": risk,
        "official_calendar_authenticated": False, "fill_certified": False,
        "historical_PIT_verified": False, "historical_OOS_validated": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
