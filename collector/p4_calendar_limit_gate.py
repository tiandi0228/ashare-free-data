"""Conservative calendar and price-limit execution evidence gate (NO TRADES).

Never infer fills from daily OHLC alone. The historical exchange calendar,
security-specific price limit and order-book execution evidence are mandatory.
"""
from datetime import date
from decimal import Decimal

def check_execution(*,entry_day,exit_day,calendar_sessions,security_limit_up,security_limit_down,observed_low,observed_high,side,order_limit_price,orderbook_fill_evidence=False):
    start=date.fromisoformat(entry_day);end=date.fromisoformat(exit_day)
    if end<=start:raise ValueError("T+1 date violated")
    if not isinstance(calendar_sessions,list) or not calendar_sessions or len(calendar_sessions)!=len(set(calendar_sessions)):
        raise ValueError("historical calendar missing or duplicate sessions")
    days=[date.fromisoformat(x) for x in calendar_sessions]
    if days!=sorted(days) or end not in days or start not in days:
        raise ValueError("date absent or invalid historical trading calendar")
    elapsed=sum(start<d<=end for d in days)
    if side not in ("BUY","SELL"):raise ValueError("unknown side")
    lo=Decimal(str(security_limit_down));hi=Decimal(str(security_limit_up))
    minimum=Decimal(str(observed_low));maximum=Decimal(str(observed_high))
    price=Decimal(str(order_limit_price))
    if min(lo,minimum,price)<=0 or lo>hi or minimum>maximum:
        raise ValueError("invalid market prices or limits")
    if not lo<=price<=hi:
        outcome="ORDER_PRICE_OUTSIDE_LIMIT"
    elif side=="BUY" and minimum>=hi:
        outcome="LIMIT_UP_NO_FILL_ASSUMPTION"
    elif side=="SELL" and maximum<=lo:
        outcome="LIMIT_DOWN_NO_FILL_ASSUMPTION"
    elif not orderbook_fill_evidence:
        outcome="OHLC_NOT_EXECUTION_EVIDENCE"
    else:
        outcome="EVIDENCE_PRESENT_REQUIRES_INDEPENDENT_FILL_REPLAY"
    return {"phase":"P4_CALENDAR_LIMIT_EXECUTION_GATE","sessions_elapsed":elapsed,
            "outcome":outcome,"recorded_fill":False,
            "official_calendar_authenticated":False,
            "security_specific_limit_authenticated":False,
            "historical_OOS_validated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
