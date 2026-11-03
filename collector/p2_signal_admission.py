"""Fail-closed research signal admission from untrusted intraday observations.

This module NEVER outputs buy recommendations, orders or tradable candidates.
It deliberately does not turn Tencent last-price / Eastmoney minute-close
proximity into two simultaneous executable quotes. It can optionally audit a
separately supplied hypothetical risk plan, never deriving one from live prices.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from collector.ashare_trade_risk_preflight import MAINBOARD,preflight

TZ=ZoneInfo("Asia/Shanghai")
PHASE="P2_SIMULATED_SIGNAL_ADMISSION_READ_ONLY"

def _time(s):
    if not isinstance(s,str):raise ValueError("missing timestamp")
    t=dt.datetime.fromisoformat(s)
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError("naive timestamp")
    return t.astimezone(TZ)

def assess(snapshot, plan=None):
    base={"phase":PHASE,"state":"BLOCKED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],
          "buy_recommendations_authorized":False,
          "simulated_fill_verified":False,
          "realtime_execution_checks_verified":False,
          "historical_PIT_verified":False}
    if not isinstance(snapshot,dict) or (
        snapshot.get("phase")!="P1_PUBLIC_INTRADAY_RESEARCH_SNAPSHOT"
        or snapshot.get("trade_gate")!="BLOCKED"
        or snapshot.get("provider_type")!="UNOFFICIAL_WEB_ENDPOINTS"
        or snapshot.get("orders")!=[]
        or snapshot.get("executable_candidates")!=[]
        or not isinstance(snapshot.get("symbols"),dict)):
        return dict(base,reason="SOURCE_SNAPSHOT_INVALID",symbols={})
    try:asof=_time(snapshot["asof"])
    except (ValueError,KeyError,TypeError):
        return dict(base,reason="INVALID_SNAPSHOT_CLOCK",symbols={})
    if len(snapshot["symbols"])>5:
        return dict(base,reason="UNBOUNDED_RESEARCH_SNAPSHOT",symbols={})
    plans={}
    if plan is not None:
        if not isinstance(plan,list) or len(plan)>5:
            return dict(base,reason="INVALID_HYPOTHETICAL_PLANS",symbols={})
        for p in plan:
            if not isinstance(p,dict) or not isinstance(p.get("code"),str):
                return dict(base,reason="INVALID_HYPOTHETICAL_PLANS",symbols={})
            if p["code"] in plans:
                return dict(base,reason="DUPLICATE_HYPOTHETICAL_PLAN",symbols={})
            plans[p["code"]]=p
        if not set(plans).issubset(snapshot["symbols"]):
            return dict(base,reason="PLAN_SYMBOL_ABSENT_FROM_SNAPSHOT",symbols={})
    observed={}
    for code,row in sorted(snapshot["symbols"].items()):
        reasons=[]
        if not isinstance(code,str) or not MAINBOARD.fullmatch(code):
            reasons.append("OUTSIDE_SHENZHEN_SHANGHAI_MAINBOARD")
        if not isinstance(row,dict):
            reasons.append("MISSING_SYMBOL_OBSERVATION")
            row={}
        if row.get("status")=="SOURCE_UNAVAILABLE":
            reasons.append("SOURCE_UNAVAILABLE")
        quality=row.get("validation")
        cross=row.get("cross_source_diagnostic")
        if not isinstance(quality,dict) or (
                quality.get("trade_gate")!="BLOCKED" or
                quality.get("executable_quote") is not False or
                quality.get("cross_source_price_verified") is not False):
            reasons.append("QUOTE_QUALITY_UNVERIFIED")
        else:
            if quality.get("validation_issues"):
                reasons.append("QUOTE_OR_MINUTE_QUALITY_ISSUES")
            age=quality.get("quote_age_seconds")
            if type(age) not in (int,float) or not -5<=age<=15:
                reasons.append("QUOTE_FRESHNESS_NOT_CONFIRMED")
        if not isinstance(cross,dict) or (
            cross.get("trade_gate")!="BLOCKED" or
            cross.get("cross_source_price_verified") is not False or
            cross.get("executable_quote") is not False):
            reasons.append("CROSS_SOURCE_PROVENANCE_UNVERIFIED")
        else:
            if cross.get("status")!="RESEARCH_PRICE_PROXIMITY_ONLY":
                reasons.append("CROSS_SOURCE_NOT_COMPARABLE")
            reasons.append("SIMULTANEOUS_EXECUTABLE_QUOTES_NOT_VERIFIED")
        quote=row.get("quote")
        if not isinstance(quote,dict) or quote.get("code")!=code:
            reasons.append("SYMBOL_QUOTE_MISMATCH")
        else:
            try:
                qt=_time(quote["quote_time"])
                check=_time(row["checked_at"])
                if not (qt.date()==check.date()==asof.date()):
                    reasons.append("SOURCE_CLOCK_DAY_MISMATCH")
                if check>asof+dt.timedelta(minutes=2) or check<asof-dt.timedelta(minutes=5):
                    reasons.append("SOURCE_CHECK_OUTSIDE_SNAPSHOT_WINDOW")
                if not -5<=(check-qt).total_seconds()<=15:
                    reasons.append("QUOTE_EXCEEDS_15S_WINDOW")
            except (ValueError,KeyError,TypeError):
                reasons.append("SOURCE_CLOCK_INVALID")
        hypothetical=None
        if code in plans:
            hypothetical=preflight(plans[code])
            if hypothetical["status"]!="MATHEMATICALLY_FEASIBLE_NOT_EXECUTABLE":
                reasons.append("HYPOTHETICAL_RISK_PLAN_REJECTED")
            else:
                reasons.append("HYPOTHETICAL_RISK_MATH_ONLY")
        if code not in plans:
            reasons.append("NO_HYPOTHETICAL_RISK_PLAN")
        # No current independent historical PIT/ST/halts/trade calendar proof.
        reasons.append("HISTORICAL_PIT_AND_ST_STATUS_NOT_CERTIFIED")
        reasons.append("EXECUTION_FILL_AND_T_PLUS_ONE_NOT_SIMULATED")
        observed[code]={
            "admission":"RESEARCH_ONLY_NOT_ACTIONABLE",
            "reasons":list(dict.fromkeys(reasons)),
            "hypothetical_risk":hypothetical,
            "trade_gate":"BLOCKED",
            "orders":[],
            "executable_candidates":[],
        }
    return dict(base,reason="ALL_RESEARCH_SYMBOLS_NON_EXECUTABLE",
                asof=asof.isoformat(),symbols=observed,
                evaluated_symbols=len(observed),
                executable_signal_count=0)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--hypothetical-plans")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    try:
        snap=json.loads(Path(args.snapshot).read_text())
        plans=json.loads(Path(args.hypothetical_plans).read_text()) if args.hypothetical_plans else None
        result=assess(snap,plans)
    except (OSError,UnicodeError,ValueError,TypeError,json.JSONDecodeError):
        result=assess(None)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":PHASE,"reason":result["reason"],
                      "evaluated_symbols":result.get("evaluated_symbols",0),
                      "trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
