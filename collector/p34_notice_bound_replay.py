"""Replay scoped exchange notices with vendor halt rows or synthetic exit risk."""
import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

from collector.p3_calendar_source_replay import (
    FILE, FIRST, LAST, PUBLISHED, SHA, SOURCE, Text, day, notice,
)
from collector.p4_position_notional_guard import check

SH_FILE = FILE.with_name("sse-annual-2026.html")
SH_SHA = "5f87affc66bc16a49a0db5aad220780c9b93d022d1963df28da4c3e6501d4686"
SH_SOURCE = "https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml"
SH_PUBLISHED = date(2025, 12, 22)
OPEN = {"NOTICE_EXPLICIT_REOPEN", "INFERRED_WEEKDAY_OPEN"}


def sh_notice(raw):
    if hashlib.sha256(raw).hexdigest() != SH_SHA:
        raise ValueError("SSE annual notice byte hash mismatch")
    reader = Text()
    reader.feed(raw.decode("utf-8"))
    reader.close()
    body = re.sub(r"\s+", "", "".join(reader.parts))
    if "2025-12-222026年休市安排" not in body:
        raise ValueError("SSE annual notice identity mismatch")
    closed, reopen = set(), set()
    for holiday in ("中秋节", "国庆节"):
        pattern = (holiday + r"：(\d+)月(\d+)日（星期.）至(\d+)月(\d+)日（星期.）休市，"
                   r"(\d+)月(\d+)日（星期.）起照常开市")
        match = re.search(pattern, body)
        if match is None:
            raise ValueError("SSE closure interval missing")
        digits = tuple(map(int, match.groups()))
        start, end, next_day = (date(2026, *digits[i:i+2]) for i in (0, 2, 4))
        if not FIRST <= start <= end < next_day <= LAST or next_day != end + timedelta(days=1):
            raise ValueError("SSE closure interval inconsistent")
        closed.update(start + timedelta(days=i) for i in range((end-start).days + 1))
        reopen.add(next_day)
    if closed & reopen:
        raise ValueError("SSE closure and reopening conflict")
    return closed, reopen


def calendar(market, as_of, root=Path(".")):
    root = Path(root)
    if market == "SH":
        closed, reopen = sh_notice((root / SH_FILE).read_bytes())
        source, sha, published = SH_SOURCE, SH_SHA, SH_PUBLISHED
    elif market == "SZ":
        closed, reopen = notice((root / FILE).read_bytes())
        source, sha, published = SOURCE, SHA, PUBLISHED
    else:
        raise ValueError("unsupported exchange")
    cutoff = day(as_of)
    rows = {}
    for i in range((LAST - FIRST).days + 1):
        session = FIRST + timedelta(days=i)
        status = ("UNKNOWN_AS_OF" if cutoff <= published else
                  "NOTICE_HOLIDAY_CLOSED" if session in closed else
                  "NOTICE_EXPLICIT_REOPEN" if session in reopen else
                  "INFERRED_WEEKEND_CLOSED" if session.weekday() >= 5 else
                  "INFERRED_WEEKDAY_OPEN")
        rows[session.isoformat()] = status
    return {"market": market, "source_url": source, "source_sha256": sha,
            "displayed_publication_day": published.isoformat(), "as_of_day": as_of,
            "rows": rows, "first_publication_timestamp_authenticated": False,
            "full_historical_calendar_authenticated": False}


def reconcile_halt(*, market, as_of, halt_start, resume_day, vendor_status, root=Path(".")):
    """Compare a supplied halt interval with vendor labels, not issuer certification."""
    start, resume = day(halt_start), day(resume_day)
    if start >= resume or not isinstance(vendor_status, dict):
        raise ValueError("invalid halt interval or vendor status")
    if (resume - start).days > (LAST - FIRST).days:
        raise ValueError("halt comparison exceeds scoped calendar")
    if any(not start <= day(k) <= resume or v not in ("0", "1") for k, v in vendor_status.items()):
        raise ValueError("vendor rows outside interval or invalid status")
    evidence = calendar(market, as_of, root)
    rows = []
    for i in range((resume - start).days + 1):
        session = start + timedelta(days=i)
        key = session.isoformat()
        status = evidence["rows"].get(key, "UNKNOWN")
        vendor = vendor_status.get(key)
        if status.startswith("UNKNOWN"):
            outcome = "UNKNOWN_CALENDAR"
        elif status not in OPEN:
            outcome = "VENDOR_ROW_ON_SCHEDULED_CLOSURE" if vendor else "SCHEDULED_CLOSURE"
        elif vendor is None:
            outcome = "MISSING_VENDOR_ROW"
        else:
            outcome = "MATCH" if vendor == ("1" if session == resume else "0") else "STATUS_CONFLICT"
        rows.append({"day": key, "calendar": status, "vendor": vendor, "outcome": outcome})
    return {"rows": rows, "calendar_source_sha256": evidence["source_sha256"],
            "issuer_halt_notice_authenticated": False, "trade_gate": "BLOCKED", "orders": []}


def replay_exit(*, entry_day, exit_day, as_of, scenario, root=Path(".")):
    start, end = day(entry_day), day(exit_day)
    risk = check(scenario)
    evidence = calendar(risk["market"], as_of, root)
    rows = evidence["rows"]
    first, last = (rows.get(key, "UNKNOWN") for key in (entry_day, exit_day))
    reasons, elapsed = [], None
    if any(status.startswith("UNKNOWN") for status in (first, last)):
        reasons.append("UNKNOWN_CALENDAR")
    elif first not in OPEN or last not in OPEN:
        reasons.append("SCHEDULED_CLOSURE")
    elif end <= start:
        reasons.append("TPLUS1_NOT_MET")
    else:
        elapsed = sum(entry_day < key <= exit_day and status in OPEN
                      for key, status in rows.items())
    if not risk["within_position_three_percent_stop_budget"]:
        reasons.append("POSITION_NET_STOP_BUDGET_EXCEEDED")
    if not risk["within_cash_budget"]:
        reasons.append("CASH_BUDGET_EXCEEDED")
    return {"elapsed_scheduled_sessions": elapsed, "blocking_reasons": reasons,
            "calendar_source_sha256": evidence["source_sha256"], "risk": risk,
            "fill_certified": False, "historical_PIT_verified": False,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}
