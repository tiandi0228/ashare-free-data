"""P4 conservative D+3 research exit decision; never emits orders.

Without intraday ordering, both stop and take-profit touched means ambiguous.
A suspension or missing execution proof stays unresolved, not a fill.
"""
from datetime import date

def exit_assessment(*,entry_day,observation_day,trading_sessions_elapsed,low,high,stop,take_profit,open_price=None,tradable=False,fill_proven=False,friday_mandatory_exit=True):
    entered=date.fromisoformat(entry_day)
    observed=date.fromisoformat(observation_day)
    if observed<=entered or type(trading_sessions_elapsed) is not int or trading_sessions_elapsed<1:
        raise ValueError("invalid T+1 observation")
    if stop<=0 or take_profit<=stop:raise ValueError("invalid stop / take profit")
    if low>high or low<=0:raise ValueError("invalid range")
    stop_hit=low<=stop
    profit_hit=high>=take_profit
    friday_exit=friday_mandatory_exit and observed.weekday()==4
    timed=trading_sessions_elapsed>=3
    reasons=[name for name,test in (("STOP",stop_hit),("TAKE_PROFIT",profit_hit),("D_PLUS_3",timed),("FRIDAY_EXIT",friday_exit)) if test]
    if stop_hit and profit_hit:
        outcome="AMBIGUOUS_BOTH_TOUCHED_CONSERVATIVE_STOP"
    elif not reasons:
        outcome="HOLD_RESEARCH_ONLY"
    elif not tradable:
        outcome="NO_VERIFIED_EXECUTION_SUSPENDED_OR_LIMITED"
    elif not fill_proven:
        outcome="EXIT_SIGNAL_UNFILLED"
    else:
        outcome="FILL_CLAIM_REQUIRES_INDEPENDENT_RECEIPT"
    return {"phase":"P4_EXIT_RESEARCH_GATE","reasons":reasons,"outcome":outcome,
            "conservative_stop_precedence":stop_hit and profit_hit,
            "recorded_fill":False,
            "historical_OOS_validated":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
