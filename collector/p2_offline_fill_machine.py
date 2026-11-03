"""Deterministic OFFLINE A-share fill/event-state simulation, never a broker.

Explicit fictitious events, supplied trading calendar, cash and fill limits.
No external quotes, inferred fills, executable signals, order routing or
auto-stop execution. Fail closed on ambiguous intrabar price order.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from collector.ashare_trade_risk_preflight import (
    D, MAINBOARD, LOT, fee, money, strict_positive, tick_price,
)

PHASE="P2_OFFLINE_FILL_STATE_MACHINE"
MAX_EVENTS=200
MAX_DAYS=30
ACTIONS=frozenset(("BUY_SUBMIT","BUY_FILL","BUY_CANCEL",
                   "SELL_SUBMIT","SELL_FILL","SELL_CANCEL","EXIT_TRIGGER"))

def day(raw):
    if not isinstance(raw,str):raise ValueError("INVALID_TRADING_DAY")
    try:
        d=dt.date.fromisoformat(raw)
    except ValueError as e:raise ValueError("INVALID_TRADING_DAY") from e
    if d.isoformat()!=raw or d.weekday()>4:
        raise ValueError("INVALID_TRADING_DAY")
    return d

def simulation(req):
    base={"phase":PHASE,"mode":"EXPLICIT_OFFLINE_EVENTS_ONLY",
          "status":"REJECTED","trade_gate":"BLOCKED",
          "buy_recommendations_authorized":False,
          "live_orders_sent":False,"simulated_fill_verified":False,
          "orders":[],"executable_candidates":[],
          "historical_PIT_verified":False,"realtime_quote_verified":False}
    try:
        if not isinstance(req,dict) or not isinstance(req.get("code"),str) or not MAINBOARD.fullmatch(req["code"]):
            raise ValueError("NOT_MAINBOARD")
        if req.get("is_st") is not False or req.get("halted") is not False:
            raise ValueError("SECURITY_STATUS_UNVERIFIED")
        cash=money(strict_positive(req["initial_cash_cny"]))
        dates=req["trading_dates"]
        if not isinstance(dates,list) or not 1<=len(dates)<=MAX_DAYS or any(day(v).isoformat()!=v for v in dates):
            raise ValueError("INVALID_TRADING_CALENDAR")
        if dates!=sorted(set(dates)):
            raise ValueError("UNORDERED_OR_DUPLICATE_CALENDAR")
        events=req["events"]
        if not isinstance(events,list) or not 1<=len(events)<=MAX_EVENTS:
            raise ValueError("INVALID_EVENT_LIST")
        holdings={} # acquisition date -> unsold shares
        pending=None
        log=[]
        last_event_key=None
        exit_intent=False
        for i,e in enumerate(events):
            if not isinstance(e,dict) or e.get("type") not in ACTIONS:
                raise ValueError("UNKNOWN_EVENT")
            action=e["type"]
            d=e.get("date")
            if d not in dates:raise ValueError("EVENT_DATE_NOT_IN_CALENDAR")
            key=(dates.index(d),i)
            if last_event_key and key<=last_event_key:raise ValueError("EVENT_ORDER_INVALID")
            last_event_key=key
            if action=="BUY_SUBMIT":
                if pending or holdings:raise ValueError("ONE_POSITION_OR_ORDER_AT_A_TIME")
                qty=e.get("shares")
                if type(qty) is not int or qty<=0 or qty%LOT:raise ValueError("BUY_LOT_NOT_100")
                price=tick_price(e["limit"])
                # Reserve ceiling for purchase + commissions, do not assume filled.
                if money(price*qty+fee(price,qty,"buy",req["code"]))>cash:
                    raise ValueError("BUY_ORDER_EXCEEDS_CASH")
                pending={"side":"BUY","date":d,"limit":price,"remaining":qty}
                log.append({"index":i,"event":action,"date":d,"state":"BUY_PENDING","remaining":qty})
            elif action=="BUY_FILL":
                if not pending or pending["side"]!="BUY" or pending["date"]!=d:
                    raise ValueError("NO_ACTIVE_BUY_ORDER")
                qty=e.get("shares")
                px=tick_price(e["price"])
                if type(qty) is not int or qty<=0 or qty>pending["remaining"] or px>pending["limit"]:
                    raise ValueError("BUY_FILL_OUTSIDE_LIMIT_OR_REMAINING")
                cost=money(px*qty+fee(px,qty,"buy",req["code"]))
                if cost>cash:raise ValueError("BUY_FILL_INSUFFICIENT_CASH")
                cash=money(cash-cost)
                holdings[d]=holdings.get(d,0)+qty
                pending["remaining"]-=qty
                remaining=pending["remaining"]
                if remaining==0:pending=None
                log.append({"index":i,"event":action,"date":d,"state":"HYPOTHETICAL_BUY_FILL",
                            "shares":qty,"price":str(px),"fee_included_cash_delta":str(-cost),
                            "pending_remaining":remaining})
            elif action=="BUY_CANCEL":
                if not pending or pending["side"]!="BUY":raise ValueError("NO_ACTIVE_BUY_ORDER")
                pending=None
                log.append({"index":i,"event":action,"date":d,"state":"BUY_REMAINDER_CANCELLED"})
            elif action=="SELL_SUBMIT":
                if pending:raise ValueError("ORDER_ALREADY_ACTIVE")
                qty=e.get("shares")
                available=sum(q for acquired,q in holdings.items() if acquired<d)
                if type(qty) is not int or qty<=0 or qty>available:
                    raise ValueError("T_PLUS_ONE_OR_INSUFFICIENT_SETTLED_SHARES")
                px=tick_price(e["limit"])
                pending={"side":"SELL","date":d,"limit":px,"remaining":qty}
                log.append({"index":i,"event":action,"date":d,"state":"SELL_PENDING","remaining":qty})
            elif action=="SELL_FILL":
                if not pending or pending["side"]!="SELL" or pending["date"]!=d:
                    raise ValueError("NO_ACTIVE_SELL_ORDER")
                qty=e.get("shares")
                px=tick_price(e["price"])
                available=sum(q for acquired,q in holdings.items() if acquired<d)
                if type(qty) is not int or qty<=0 or qty>pending["remaining"] or qty>available or px<pending["limit"]:
                    raise ValueError("SELL_FILL_OUTSIDE_LIMIT_OR_SETTLED_SHARES")
                remain=qty
                for acquired in sorted(holdings):
                    if acquired>=d:continue
                    take=min(holdings[acquired],remain)
                    holdings[acquired]-=take
                    remain-=take
                    if remain==0:break
                proceeds=money(px*qty-fee(px,qty,"sell",req["code"]))
                cash=money(cash+proceeds)
                pending["remaining"]-=qty
                left=pending["remaining"]
                if left==0:pending=None
                log.append({"index":i,"event":action,"date":d,"state":"HYPOTHETICAL_SELL_FILL",
                            "shares":qty,"price":str(px),
                            "fee_included_cash_delta":str(proceeds),"pending_remaining":left})
            elif action=="SELL_CANCEL":
                if not pending or pending["side"]!="SELL":raise ValueError("NO_ACTIVE_SELL_ORDER")
                pending=None
                log.append({"index":i,"event":action,"date":d,"state":"SELL_REMAINDER_CANCELLED"})
            elif action=="EXIT_TRIGGER":
                if not holdings or not sum(holdings.values()) or pending:
                    raise ValueError("EXIT_TRIGGER_WITHOUT_SETTLED_HOLDINGS")
                reason=e.get("reason")
                if reason not in ("STOP_LOSS","TAKE_PROFIT","TIME_EXIT"):
                    raise ValueError("INVALID_EXIT_REASON")
                if any(acquired>=d for acquired,q in holdings.items() if q>0):
                    raise ValueError("T_PLUS_ONE_EXIT_NOT_ALLOWED")
                # Same-bar stop and profit ordering requires tick-level evidence.
                if e.get("same_bar_both_touched") is not False:
                    raise ValueError("AMBIGUOUS_INTRABAR_EXIT")
                if reason=="TIME_EXIT":
                    oldest=min(acquired for acquired,q in holdings.items() if q>0)
                    days=dates.index(d)-dates.index(oldest)
                    if not 3<=days<=5:raise ValueError("TIME_EXIT_NOT_3_TO_5_TRADING_DAYS")
                exit_intent=True
                log.append({"index":i,"event":action,"date":d,
                            "state":"EXIT_INTENT_ONLY_NOT_EXECUTED","reason":reason})
        return dict(base,status="OFFLINE_SCENARIO_REPLAYED_NOT_EXECUTABLE",
                    code=req["code"],remaining_cash_cny=str(cash),
                    remaining_shares=sum(holdings.values()),
                    open_simulated_order=(
                        {"side":pending["side"],"remaining":pending["remaining"]}
                        if pending else None),
                    exit_intent_observed=exit_intent,
                    simulation_events=log,
                    limitations=["EVENTS_SUPPLIED_NOT_EXCHANGE_CONFIRMED",
                                 "NO_REAL_ORDER_BOOK_OR_FILL_PROOF",
                                 "NO_BROKER_OR_EXCHANGE_SESSION",
                                 "NOT_A_CERTIFIED_TRADING_CALENDAR"])
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
        msg=str(exc)
        safe=msg if msg in {
            "NOT_MAINBOARD","SECURITY_STATUS_UNVERIFIED","INVALID_TRADING_CALENDAR",
            "UNORDERED_OR_DUPLICATE_CALENDAR","INVALID_EVENT_LIST","UNKNOWN_EVENT",
            "EVENT_DATE_NOT_IN_CALENDAR","EVENT_ORDER_INVALID","ONE_POSITION_OR_ORDER_AT_A_TIME",
            "BUY_LOT_NOT_100","BUY_ORDER_EXCEEDS_CASH","NO_ACTIVE_BUY_ORDER",
            "BUY_FILL_OUTSIDE_LIMIT_OR_REMAINING","BUY_FILL_INSUFFICIENT_CASH",
            "ORDER_ALREADY_ACTIVE","T_PLUS_ONE_OR_INSUFFICIENT_SETTLED_SHARES",
            "NO_ACTIVE_SELL_ORDER","SELL_FILL_OUTSIDE_LIMIT_OR_SETTLED_SHARES",
            "EXIT_TRIGGER_WITHOUT_SETTLED_HOLDINGS","INVALID_EXIT_REASON",
            "T_PLUS_ONE_EXIT_NOT_ALLOWED","AMBIGUOUS_INTRABAR_EXIT",
            "TIME_EXIT_NOT_3_TO_5_TRADING_DAYS",
        } else "INVALID_OR_UNVERIFIABLE_EVENT_EVIDENCE"
        return dict(base,reason=safe)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scenario",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:res=simulation(json.loads(Path(a.scenario).read_text()))
    except (OSError,ValueError,UnicodeError):res=simulation(None)
    dst=Path(a.out);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":res["status"],"trade_gate":"BLOCKED",
                      "reason":res.get("reason")},ensure_ascii=False))
if __name__=="__main__":main()
