"""Fail-closed issuer session status gate for V2.2 research-only execution."""
from datetime import date

def check(*,issuer,session_day,official_calendar_sessions,issuer_status,official_status_authenticated=False,official_calendar_authenticated=False,market_orderbook_evidence=False):
    day=date.fromisoformat(session_day)
    if not isinstance(official_calendar_sessions,list) or len(official_calendar_sessions)!=len(set(official_calendar_sessions)):
        raise ValueError("invalid calendar")
    days=[date.fromisoformat(x) for x in official_calendar_sessions]
    if days!=sorted(days):raise ValueError("unordered calendar")
    if not isinstance(issuer,str) or not issuer.startswith(("sh.","sz.")):raise ValueError("invalid issuer")
    if issuer_status not in ("TRADING","SUSPENDED","UNKNOWN"):
        raise ValueError("invalid status")
    if day not in days:outcome="MARKET_CLOSED_OR_SESSION_NOT_PROVEN"
    elif not official_calendar_authenticated:outcome="OFFICIAL_SESSION_CALENDAR_UNAUTHENTICATED"
    elif not official_status_authenticated:outcome="ISSUER_STATUS_UNAUTHENTICATED"
    elif issuer_status=="SUSPENDED":outcome="ISSUER_SUSPENDED_NO_EXECUTION"
    elif issuer_status=="UNKNOWN":outcome="ISSUER_STATUS_UNKNOWN_BLOCKED"
    elif not market_orderbook_evidence:outcome="TRADING_STATUS_NOT_FILL_EVIDENCE"
    else:outcome="SOURCE_EVIDENCE_NEEDS_INDEPENDENT_FILL_REPLAY"
    return {"phase":"P4_V22_ISSUER_SESSION_EXECUTION_GATE","issuer":issuer,"session_day":session_day,
            "outcome":outcome,"fill_verified":False,"historical_OOS_validated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
