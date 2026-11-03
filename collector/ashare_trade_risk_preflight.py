"""Conservative A-share MAINBOARD 3–5 day risk preflight (NO TRADES).

A bounded *illustrative* order-size/cost calculation, never buy authorization.
Inputs are hypothetical and must be independently authenticated elsewhere.
All money arithmetic uses Decimal and rounds per cash fee to fen.
"""
import argparse
import decimal
import json
import re
from pathlib import Path

D=decimal.Decimal
CENT=D("0.01")
COMMISSION_RATE=D("0.0002854")  # agreed broker example, 0.2854 per mille
COMMISSION_MIN=D("5.00")
STAMP_SELL=D("0.0005")
SH_TRANSFER=D("0.00001")
MAX_LOSS_RATE=D("0.03")
MIN_REWARD_RISK=D("2")
TICK=D("0.01")
LOT=100
MAINBOARD=re.compile(r"(?:00\d{4}|60\d{4})\Z")

def money(x):
    return x.quantize(CENT,rounding=decimal.ROUND_HALF_UP)

def strict_positive(raw):
    if isinstance(raw,bool) or isinstance(raw,(dict,list)):
        raise ValueError("not a decimal")
    if isinstance(raw,float):raise ValueError("binary floats prohibited; use decimal strings")
    try:v=D(str(raw))
    except (decimal.InvalidOperation,ValueError) as e:raise ValueError("invalid decimal") from e
    if not v.is_finite() or v<=0:raise ValueError("not finite positive")
    return v

def tick_price(raw):
    v=strict_positive(raw)
    if v!=v.quantize(TICK) or (v/TICK)!=v/TICK//1:
        raise ValueError("prices must be 0.01 tick aligned")
    return v

def fee(price,shares,side,code):
    gross=price*shares
    commission=max(COMMISSION_MIN,money(gross*COMMISSION_RATE))
    transfer=money(gross*SH_TRANSFER) if code.startswith("60") else D("0")
    stamp=money(gross*STAMP_SELL) if side=="sell" else D("0")
    return money(commission+transfer+stamp)

def preflight(req):
    base={"phase":"ASHARE_MAINBOARD_TRADE_RISK_PREFLIGHT",
          "mode":"HYPOTHETICAL_MATH_ONLY",
          "trade_gate":"BLOCKED","buy_recommendations_authorized":False,
          "orders":[],"executable_candidates":[],
          "realtime_quote_verified":False,"historical_PIT_verified":False,
          "t_plus_one_enforced":True}
    if not isinstance(req,dict):
        return dict(base,status="REJECTED",reasons=["INVALID_REQUEST"])
    reasons=[]
    code=req.get("code")
    if not isinstance(code,str) or not MAINBOARD.fullmatch(code):
        reasons.append("NOT_SHENZHEN_SHANGHAI_MAINBOARD")
    if req.get("is_st") is not False:
        reasons.append("NON_ST_STATUS_NOT_CONFIRMED")
    if req.get("halted") is not False:
        reasons.append("NOT_HALTED_STATUS_NOT_CONFIRMED")
    if req.get("holding_days") not in (3,4,5) or type(req.get("holding_days")) is not int:
        reasons.append("HOLDING_WINDOW_NOT_3_TO_5_TRADING_DAYS")
    if reasons:
        return dict(base,status="REJECTED",reasons=reasons)
    try:
        capital=strict_positive(req["capital_cny"])
        entry=tick_price(req["entry"])
        stop=tick_price(req["stop"])
        target=tick_price(req["target"])
    except (KeyError,ValueError):
        return dict(base,status="REJECTED",reasons=["INVALID_FINANCIAL_INPUT"])
    if not(stop<entry<target):
        return dict(base,status="REJECTED",reasons=["STOP_ENTRY_TARGET_ORDER_INVALID"])
    # Conservative lots only: avoid imaginary fractional/odd-lot entry sizing.
    max_lots=int(capital/(entry*LOT))
    best=None
    for lots in range(max_lots,0,-1):
        shares=lots*LOT
        buy=money(entry*shares+fee(entry,shares,"buy",code))
        if buy>capital:continue
        loss=money(buy-(stop*shares-fee(stop,shares,"sell",code)))
        reward=money(target*shares-fee(target,shares,"sell",code)-buy)
        limit=money(capital*MAX_LOSS_RATE)
        ratio=reward/loss if loss>0 else D("-1")
        if loss>0 and loss<=limit and reward>0 and ratio>=MIN_REWARD_RISK:
            best=(shares,buy,loss,reward,limit,ratio)
            break
    if best is None:
        return dict(base,status="REJECTED",reasons=["NO_LOT_FITS_BUDGET_NET_RISK_AND_RR"],
                    capital_cny=str(money(capital)),
                    max_loss_cny=str(money(capital*MAX_LOSS_RATE)))
    shares,buy,loss,reward,limit,ratio=best
    return dict(base,status="MATHEMATICALLY_FEASIBLE_NOT_EXECUTABLE",reasons=[
                "QUOTE_FRESHNESS_UNVERIFIED",
                "MARKET_FILL_AND_SLIPPAGE_UNVERIFIED",
                "HISTORICAL_PIT_AND_STRATEGY_NOT_VERIFIED",
                "BROKER_REAL_FEE_SCHEDULE_NOT_VERIFIED"],
                code=code,shares=shares,entry=str(entry),stop=str(stop),
                target=str(target),holding_trading_days=req["holding_days"],
                cash_required_cny=str(buy),planned_net_loss_cny=str(loss),
                planned_net_reward_cny=str(reward),max_allowed_loss_cny=str(limit),
                planned_net_reward_risk=str(ratio.quantize(D("0.0001"),
                    rounding=decimal.ROUND_DOWN)),
                fee_model="commission 0.2854‰ min ¥5 each side; sell stamp 0.5‰; SH transfer 0.01‰ each side; no slippage included")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        result=preflight(json.loads(Path(a.input).read_text()))
    except (OSError,ValueError,json.JSONDecodeError):
        result=preflight(None)
    output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"trade_gate":"BLOCKED",
                      "reasons":result["reasons"]},ensure_ascii=False))
if __name__=="__main__":main()
