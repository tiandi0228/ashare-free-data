"""Frozen D+3 to D+5 time-exit monitoring; never infer a sell from daily OHLC."""
from datetime import date

def assess(*,entry_day,observation_day,calendar_sessions,preflight,receipt_verified=False,
           earliest_exit_sessions=3,latest_exit_sessions=5):
    if earliest_exit_sessions!=3 or latest_exit_sessions!=5:
        raise ValueError("V2.2 research window must be explicitly frozen to 3-5 sessions")
    entry=date.fromisoformat(entry_day);observed=date.fromisoformat(observation_day)
    if observed<=entry:raise ValueError("T+1 needed")
    if not isinstance(calendar_sessions,list) or len(calendar_sessions)!=len(set(calendar_sessions)):
        raise ValueError("invalid trading sessions")
    days=[date.fromisoformat(x) for x in calendar_sessions]
    if days!=sorted(days) or entry not in days or observed not in days:
        raise ValueError("unverified session date")
    if preflight.get("phase")!="P4_UNIFIED_EXECUTION_RESEARCH_PREFLIGHT" or preflight.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid preflight provenance")
    if preflight.get("fill_certified") is not False or preflight.get("orders")!=[]:
        raise ValueError("unsafe preflight")
    elapsed=sum(entry<d<=observed for d in days)
    if elapsed<3:state="BEFORE_TIME_EXIT_WINDOW"
    elif elapsed<=5:state="EXIT_WINDOW_RESEARCH_ONLY"
    else:state="OVERDUE_EXIT_UNRESOLVED"
    if elapsed>=3:
        if not preflight.get("candidate_for_independent_receipt_replay"):
            state="EXIT_BLOCKED_UNRESOLVED" if elapsed<=5 else "OVERDUE_EXIT_BLOCKED"
        elif not receipt_verified:
            state="EXIT_RECEIPT_MISSING_UNRESOLVED" if elapsed<=5 else "OVERDUE_RECEIPT_MISSING"
        else:
            state="EXIT_RECEIPT_OBSERVED_UNCERTIFIED"
    return {"phase":"P4_V22_TIME_EXIT_RESEARCH","entry_day":entry_day,
            "observation_day":observation_day,"sessions_elapsed":elapsed,"state":state,
            "forced_fill_assumed":False,"return_finalized":False,
            "historical_OOS_validated":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
