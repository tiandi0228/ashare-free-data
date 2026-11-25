"""Fail-closed issuer session status gate for V2.2 research-only execution.

This is an input-shape check, not official status authentication or proof
that a broker can fill an order.
"""
from datetime import date
import re

# This P4 strategy explicitly excludes ChiNext, STAR, BSE and other boards.
MAIN_BOARD = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")


def _session_date(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        raise ValueError("invalid session date")
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("invalid session date") from exc
    if parsed.isoformat() != raw or parsed.weekday() >= 5:
        raise ValueError("invalid session date")
    return parsed


def check(*, issuer, session_day, official_calendar_sessions, issuer_status,
          official_status_authenticated=False, official_calendar_authenticated=False,
          market_orderbook_evidence=False):
    if not isinstance(issuer, str) or not MAIN_BOARD.fullmatch(issuer):
        raise ValueError("invalid issuer")
    if any(type(flag) is not bool for flag in (
            official_status_authenticated, official_calendar_authenticated,
            market_orderbook_evidence)):
        raise ValueError("invalid authentication flag")
    if issuer_status not in ("TRADING", "SUSPENDED", "UNKNOWN"):
        raise ValueError("invalid status")
    day = _session_date(session_day)
    if not isinstance(official_calendar_sessions, list):
        raise ValueError("invalid calendar")
    days = [_session_date(x) for x in official_calendar_sessions]
    if days != sorted(set(days)):
        raise ValueError("unordered or duplicate calendar")
    if day not in days:
        outcome = "MARKET_CLOSED_OR_SESSION_NOT_PROVEN"
    elif not official_calendar_authenticated:
        outcome = "OFFICIAL_SESSION_CALENDAR_UNAUTHENTICATED"
    elif not official_status_authenticated:
        outcome = "ISSUER_STATUS_UNAUTHENTICATED"
    elif issuer_status == "SUSPENDED":
        outcome = "ISSUER_SUSPENDED_NO_EXECUTION"
    elif issuer_status == "UNKNOWN":
        outcome = "ISSUER_STATUS_UNKNOWN_BLOCKED"
    elif not market_orderbook_evidence:
        outcome = "TRADING_STATUS_NOT_FILL_EVIDENCE"
    else:
        outcome = "SOURCE_EVIDENCE_NEEDS_INDEPENDENT_FILL_REPLAY"
    return {
        "phase": "P4_V22_ISSUER_SESSION_EXECUTION_GATE",
        "issuer": issuer, "session_day": session_day,
        "outcome": outcome,
        "fill_verified": False, "historical_OOS_validated": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
