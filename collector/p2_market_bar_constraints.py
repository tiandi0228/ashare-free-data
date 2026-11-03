"""Read-only A-share historical bar/limit/volume plausibility preflight.

This module does NOT establish that a submitted bar exists, that a price was
reachable in the exchange order book, or that any simulated fill occurred.
Prices, calendars and security statuses must be independently verified before
a research result may be promoted. Never permits trades.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
from collector.ashare_trade_risk_preflight import D, MAINBOARD, tick_price

PHASE="P2_MARKET_BAR_CONSTRAINT_PREFLIGHT"
MAX_BARS=260
def check(payload):
    base={"phase":PHASE,"state":"REJECTED","trade_gate":"BLOCKED",
          "buy_recommendations_authorized":False,"simulated_fill_verified":False,
          "trade_calendar_certified":False,"limit_prices_certified":False,
          "orders":[],"executable_candidates":[]}
    if not isinstance(payload,dict) or not isinstance(payload.get("code"),str) or not MAINBOARD.fullmatch(payload["code"]):
        return dict(base,reasons=["INVALID_MAINBOARD_SYMBOL"])
    if payload.get("is_st") is not False or payload.get("halted") is not False:
        return dict(base,reasons=["SECURITY_STATUS_UNVERIFIED"])
    bars=payload.get("bars")
    if not isinstance(bars,list) or not 1<=len(bars)<=MAX_BARS:
        return dict(base,reasons=["INVALID_BAR_SERIES"])
    seen=set()
    issues=[]
    last=None
    previous_date=None
    for i,bar in enumerate(bars):
        if not isinstance(bar,dict):
            issues.append(f"BAR_{i}_INVALID");continue
        try:
            stamp=dt.datetime.fromisoformat(bar["time"])
            if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.utcoffset()!=dt.timedelta(hours=8):
                raise ValueError("not China timezone")
            if stamp.weekday()>4 or not (
                dt.time(9,30)<=stamp.time()<=dt.time(11,30) or
                dt.time(13,1)<=stamp.time()<=dt.time(15,0)):
                issues.append(f"BAR_{i}_OUTSIDE_CONTINUOUS_SESSION")
            if stamp in seen or (last is not None and stamp<=last):
                issues.append(f"BAR_{i}_UNORDERED_OR_DUPLICATE")
            seen.add(stamp)
            last=stamp
            low=tick_price(bar["low"])
            high=tick_price(bar["high"])
            op=tick_price(bar["open"])
            close=tick_price(bar["close"])
            lower=tick_price(bar["daily_lower_limit"])
            upper=tick_price(bar["daily_upper_limit"])
            if not(lower<=low<=min(op,close)<=max(op,close)<=high<=upper):
                issues.append(f"BAR_{i}_OHLC_OR_DAILY_LIMIT_CONFLICT")
            if previous_date==stamp.date():
                pass
            previous_date=stamp.date()
            volume=bar["volume_shares"]
            if type(volume) is not int or volume<0:
                issues.append(f"BAR_{i}_INVALID_VOLUME")
            if type(bar.get("is_final")) is not bool or bar["is_final"] is not True:
                issues.append(f"BAR_{i}_UNFINALIZED")
        except (KeyError,TypeError,ValueError,ArithmeticError):
            issues.append(f"BAR_{i}_MALFORMED")
    # Exchange limit prices are supplied as evidence candidates, NOT
    # computed from a possibly unadjusted previous close. Price-limit rules
    # depend on board, listing age, ST and specific historical exceptions.
    return dict(base,state=("STRUCTURAL_PLAUSIBILITY_ONLY_NOT_EXECUTABLE" if not issues else "REJECTED"),
                inspected_bars=len(bars),reasons=issues or [
                    "NO_INDEPENDENT_EXCHANGE_PRICE_LIMIT_PROVENANCE",
                    "NO_TRUSTED_HOLIDAY_AND_SESSION_CALENDAR",
                    "VOLUME_NOT_ORDER_BOOK_LIQUIDITY",
                    "PRICE_TOUCH_DOES_NOT_PROVE_LIMIT_ORDER_FILL"],
                limitations=["NO_EXTERNAL_PROVENANCE_OF_BAR_PRICES_OR_VOLUME",
                             "NOT_PROOF_OF_FILLS_OR_ORDER_QUEUE_POSITION",
                             "NOT_HISTORICAL_PIT_CERTIFICATION"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:result=check(json.loads(Path(a.input).read_text()))
    except (OSError,ValueError,UnicodeError):result=check(None)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"state":result["state"],"trade_gate":"BLOCKED",
                      "inspected_bars":result.get("inspected_bars",0)}))
if __name__=="__main__":main()
