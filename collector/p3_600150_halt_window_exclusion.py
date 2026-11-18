"""Research-only 600150 halt-window conservative candidate blocker.

This is an issuer notice-derived *do-not-execute* overlay. It cannot certify
official historical daily state; outside its listed days is UNKNOWN, not OPEN.
"""
from datetime import date, timedelta
from collector.p3_600150_dated_media_crosscheck import build as media_build

START = date(2025, 8, 13)
END = date(2025, 8, 18)
RESUME = date(2025, 8, 19)
EXPECTED = {
    "1224387134": ("HALT_START", "2025-08-13"),
    "1224504273": ("RESUME_START", "2025-08-19"),
}


def overlay(media=None):
    if media is None:
        media = media_build()
    if (not isinstance(media, dict)
        or media.get("phase") != "P3_600150_DATED_MEDIA_CROSSCHECK_RESEARCH"
        or media.get("trade_gate") != "BLOCKED"
        or media.get("orders") != []
        or media.get("executable_candidates") != []
        or media.get("official_historical_PIT_verified") is not False
        or type(media.get("independently_authenticated_first_publication_instants")) is not int
        or media["independently_authenticated_first_publication_instants"] != 0
        or type(media.get("historical_notice_days_crossreferenced")) is not int
        or media["historical_notice_days_crossreferenced"] != 2):
        raise ValueError("unauthenticated or unsafe research input")
    rows = media.get("rows")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("missing notices")
    seen = set()
    for r in rows:
        if not isinstance(r, dict) or r.get("announcement_id") not in EXPECTED:
            raise ValueError("wrong notice")
        ident = r["announcement_id"]
        if ident in seen:
            raise ValueError("duplicate notice")
        seen.add(ident)
        role, day = EXPECTED[ident]
        if (r.get("issuer") != "sh.600150"
            or r.get("research_event") != role
            or r.get("effective_date_claim_from_issuer_notice") != day
            or r.get("publication_time_of_day_authenticated") is not False
            or r.get("publisher_origin_independently_authenticated") is not False
            or r.get("exchange_effective_interval_authenticated") is not False
            or r.get("complete_historical_PIT_state_authenticated") is not False
            or r.get("candidate_asof_trade_eligible") is not False):
            raise ValueError("promoted or contradictory notice")
    if seen != set(EXPECTED):
        raise ValueError("missing notice identity")
    # Days between explicit issuer-claimed halt start and explicit resume date.
    # Weekdays are research labels only, not an authenticated SSE calendar.
    blocked = []
    d = START
    while d < RESUME:
        if d.weekday() < 5:
            blocked.append(d.isoformat())
        d += timedelta(days=1)
    if blocked != ["2025-08-13", "2025-08-14", "2025-08-15", "2025-08-18"]:
        raise ValueError("unexpected calendar assumptions")
    return {
        "phase": "P3_600150_CONSERVATIVE_HALT_WINDOW_OVERLAY",
        "issuer": "sh.600150",
        "source_notice_ids": sorted(EXPECTED),
        "issuer_claimed_halt_start": START.isoformat(),
        "issuer_claimed_halt_end": END.isoformat(),
        "issuer_claimed_resume_day": RESUME.isoformat(),
        "research_weekday_exclusion_dates": blocked,
        "exclusion_basis": "ISSUER_PDF_TEXT_CLAIM_RESEARCH_NOT_SSE_CERTIFICATION",
        "outside_window_status": "UNKNOWN_NOT_CERTIFIED_TRADABLE",
        "full_historical_issuer_state_verified": False,
        "official_first_publication_authenticated": False,
        "historical_PIT_verified": False,
        "fills_verified": 0,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def may_execute_on_day(report, day):
    """Fail-closed: an exclusion is one-way, never trade authorization."""
    if (not isinstance(report, dict)
        or report.get("phase") != "P3_600150_CONSERVATIVE_HALT_WINDOW_OVERLAY"
        or report.get("trade_gate") != "BLOCKED"
        or report.get("orders") != []
        or report.get("executable_candidates") != []
        or report.get("full_historical_issuer_state_verified") is not False
        or report.get("historical_PIT_verified") is not False):
        raise ValueError("unsafe halt research overlay")
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("invalid day")
    return False


if __name__ == "__main__":
    import json
    print(json.dumps(overlay(), ensure_ascii=False, indent=2))
