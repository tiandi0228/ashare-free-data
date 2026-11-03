"""Offline replay evidence gate linking hypothetical fills to structural bars.

Never proves an exchange fill: a bar high/low and total market volume cannot
establish order-book position, queue priority, counterparty or slippage. This
gate only rejects impossible or inconsistent *user-supplied* scenarios. Every
result is research-only BLOCKED.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from collector.ashare_trade_risk_preflight import D, tick_price
from collector.p2_market_bar_constraints import check as bar_check
from collector.p2_offline_fill_machine import simulation

PHASE="P2_BACKTEST_FILL_EVIDENCE_JOIN"
FILL_EVENTS=frozenset(("BUY_FILL","SELL_FILL"))

def _stamp(raw):
    if not isinstance(raw,str):
        raise ValueError("FILL_BAR_TIMESTAMP_MISSING")
    try: stamp=dt.datetime.fromisoformat(raw)
    except ValueError as e:raise ValueError("FILL_BAR_TIMESTAMP_INVALID") from e
    if stamp.tzinfo is None or stamp.utcoffset()!=dt.timedelta(hours=8):
        raise ValueError("FILL_BAR_TIMESTAMP_INVALID")
    return stamp

def join(scenario,bars):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],
          "buy_recommendations_authorized":False,
          "simulated_fill_verified":False,
          "historical_PIT_verified":False,
          "realtime_quote_verified":False,
          "market_bar_provenance_verified":False}
    def fail(reason):
        return dict(base,reason=reason)
    try:
        if not isinstance(scenario,dict) or not isinstance(bars,dict) or (
            scenario.get("code")!=bars.get("code") or
            scenario.get("is_st") is not bars.get("is_st") or
            scenario.get("halted") is not bars.get("halted")
        ):
            return fail("SCENARIO_BAR_IDENTITY_MISMATCH")
        bar_result=bar_check(bars)
        if bar_result.get("state")!="STRUCTURAL_PLAUSIBILITY_ONLY_NOT_EXECUTABLE":
            return fail("BAR_PREFLIGHT_REJECTED")
        fill_result=simulation(scenario)
        if fill_result.get("status")!="OFFLINE_SCENARIO_REPLAYED_NOT_EXECUTABLE":
            return fail("SIMULATED_EVENT_REPLAY_REJECTED")
        lookup={}
        for item in bars["bars"]:
            key=_stamp(item["time"])
            lookup[key]=(tick_price(item["low"]),tick_price(item["high"]),
                         item["volume_shares"])
        per_bar={}
        last_time=None
        examined=0
        for event in scenario["events"]:
            if event["type"] not in FILL_EVENTS:
                continue
            stamp=_stamp(event.get("bar_time"))
            if last_time is not None and stamp<last_time:
                return fail("FILL_TIMESTAMPS_OUT_OF_ORDER")
            last_time=stamp
            if stamp.date().isoformat()!=event["date"]:
                return fail("FILL_BAR_EVENT_TRADING_DAY_MISMATCH")
            row=lookup.get(stamp)
            if row is None:
                return fail("NO_EXACT_FINAL_BAR_FOR_FILL")
            low,high,total=row
            price=tick_price(event["price"])
            if not(low<=price<=high):
                return fail("FILL_PRICE_OUTSIDE_BAR_RANGE")
            used=per_bar.get(stamp,0)+event["shares"]
            if used>total:
                return fail("FILL_SHARES_EXCEED_BAR_MARKET_VOLUME")
            per_bar[stamp]=used
            examined+=1
        if not examined:
            return fail("NO_EXPLICIT_FILL_EVENTS")
        return dict(base,status="STRUCTURAL_REPLAY_PLAUSIBLE_NOT_EXECUTABLE",
                    checked_explicit_fill_events=examined,
                    checked_distinct_bars=len(per_bar),
                    limitations=[
                        "MARKET_BAR_VOLUME_NOT_AVAILABLE_QUEUE_LIQUIDITY",
                        "PRICE_INSIDE_BAR_NOT_PROOF_OF_EXECUTION",
                        "EXPLICIT_FILLS_NOT_EXCHANGE_ATTESTED",
                        "TRADING_CALENDAR_AND_PIT_NOT_CERTIFIED",
                    ])
    except (ValueError,KeyError,TypeError,ArithmeticError):
        return fail("UNVERIFIABLE_REPLAY_EVIDENCE")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scenario",required=True)
    p.add_argument("--bars",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    try:
        result=join(json.loads(Path(args.scenario).read_text()),
                    json.loads(Path(args.bars).read_text()))
    except (OSError,ValueError,UnicodeError):
        result=join(None,None)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"trade_gate":"BLOCKED",
                      "reason":result.get("reason")},ensure_ascii=False))
if __name__=="__main__":main()
