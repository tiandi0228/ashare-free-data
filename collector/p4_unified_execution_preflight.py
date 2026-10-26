"""Compose independent P4 evidence gates; every result stays non-executable."""
from collector.p4_calendar_limit_gate import check_execution
from collector.p4_issuer_session_gate import check as check_session

def assess(*,issuer,entry_day,exit_day,calendar_sessions,issuer_status,
           official_status_authenticated=False,official_calendar_authenticated=False,
           security_limit_authenticated=False,security_limit_up=None,security_limit_down=None,
           observed_low=None,observed_high=None,side=None,order_limit_price=None,
           orderbook_fill_evidence=False):
    session=check_session(issuer=issuer,session_day=exit_day,
        official_calendar_sessions=calendar_sessions,issuer_status=issuer_status,
        official_status_authenticated=official_status_authenticated,
        official_calendar_authenticated=official_calendar_authenticated,
        market_orderbook_evidence=orderbook_fill_evidence)
    reasons=[]
    if session["outcome"]!="SOURCE_EVIDENCE_NEEDS_INDEPENDENT_FILL_REPLAY":
        reasons.append(session["outcome"])
    if not security_limit_authenticated:
        reasons.append("SECURITY_PRICE_LIMIT_UNAUTHENTICATED")
    price_result=None
    if all(v is not None for v in (security_limit_up,security_limit_down,observed_low,observed_high,side,order_limit_price)):
        price_result=check_execution(entry_day=entry_day,exit_day=exit_day,
            calendar_sessions=calendar_sessions,security_limit_up=security_limit_up,
            security_limit_down=security_limit_down,observed_low=observed_low,
            observed_high=observed_high,side=side,order_limit_price=order_limit_price,
            orderbook_fill_evidence=orderbook_fill_evidence)
        if price_result["outcome"]!="EVIDENCE_PRESENT_REQUIRES_INDEPENDENT_FILL_REPLAY":
            reasons.append(price_result["outcome"])
    else:
        reasons.append("PRICE_OR_QUOTE_EVIDENCE_MISSING")
    return {"phase":"P4_UNIFIED_EXECUTION_RESEARCH_PREFLIGHT","issuer":issuer,
       "session_outcome":session["outcome"],
       "price_outcome":price_result["outcome"] if price_result else None,
       "blocking_reasons":reasons,
       "candidate_for_independent_receipt_replay":not reasons,
       "fill_certified":False,"historical_OOS_validated":False,
       "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
