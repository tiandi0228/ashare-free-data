"""Strict 3% of EACH position notional including both-side fees and fill slippage.

Independent expressly SYNTHETIC audit for P4 contract gap. The private trading
strategy must re-review this rule; this public module never issues trades.
"""
from __future__ import annotations
import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path

CENT = Decimal("0.01")
RISK = Decimal("0.03")
COMMISSION = Decimal("0.0002854")
MIN_FEE = Decimal("5")
SELL_STAMP = Decimal("0.0005")
SH_TRANSFER = Decimal("0.00001")

def exact(value, field):
    if isinstance(value,bool) or not isinstance(value,(str,int,Decimal)):
        raise ValueError(field+": exact decimal required")
    try: n=Decimal(value)
    except (InvalidOperation,ValueError):
        raise ValueError(field+": invalid decimal") from None
    if not n.is_finite():
        raise ValueError(field+": non-finite decimal")
    return n

def money(n):
    return n.quantize(CENT,rounding=ROUND_HALF_UP)

def fees(notional,market,side):
    if market not in ("SH","SZ") or side not in ("BUY","SELL") or notional<=0:
        raise ValueError("Unsupported exchange/side/amount")
    commission=money(max(MIN_FEE,notional*COMMISSION))
    stamp=money(notional*SELL_STAMP) if side=="SELL" else Decimal("0.00")
    transfer=money(notional*SH_TRANSFER) if market=="SH" else Decimal("0.00")
    return commission+stamp+transfer

def check(scenario):
    if not isinstance(scenario,dict) or scenario.get("synthetic_test_case") is not True:
        raise ValueError("No live stock or unlabelled scenario accepted")
    if any(k in scenario for k in ("ticker","code","security_code","slippage_fee",
                                   "slippage_deduction","spread_fee")):
        raise ValueError("No ticker inputs or duplicate slippage charges accepted")
    required=("market","entry_actual_fill","stop_exit_actual_fill","shares")
    if any(k not in scenario for k in required):
        raise ValueError("Actual-fill assumptions and shares are required")
    market=scenario["market"]
    if market not in ("SH","SZ"):
        raise ValueError("SH or SZ only")
    qty=scenario["shares"]
    if type(qty) is not int or qty<100 or qty%100:
        raise ValueError("Explicit 100-share lots required")
    entry=exact(scenario["entry_actual_fill"],"entry_actual_fill")
    exitp=exact(scenario["stop_exit_actual_fill"],"stop_exit_actual_fill")
    if entry<=0 or exitp<=0 or exitp>=entry:
        raise ValueError("Long synthetic stop must be below entry")
    if entry%CENT or exitp%CENT:
        raise ValueError("Fill assumptions must be on CNY 0.01 tick grid")
    initial=entry*qty
    stop_value=exitp*qty
    buy_fees=fees(initial,market,"BUY")
    sell_fees=fees(stop_value,market,"SELL")
    modeled_loss=money(initial+buy_fees-stop_value+sell_fees)
    position_risk_cap=money(initial*RISK)
    account_cap=money(Decimal("8000")*RISK)  # diagnostic only, NEVER risk denominator
    cash=exact(scenario.get("cash_available","8000.00"),"cash_available")
    if cash<0 or cash>Decimal("8000.00"):
        raise ValueError("Synthetic account cash out of bounds")
    within_cash=money(initial+buy_fees)<=cash
    within_risk=modeled_loss<=position_risk_cap
    return {
        "phase":"P4_POSITION_NOTIONAL_RISK_POLICY_TEST",
        "status":"SYNTHETIC_RISK_POLICY_CHECK_ONLY",
        "synthetic_test_case":True,
        "market":market,
        "shares":qty,
        "entry_actual_fill_assumption":str(entry),
        "stop_exit_actual_fill_assumption":str(exitp),
        "slippage_already_in_actual_fill_prices":True,
        "buy_notional_yuan":str(money(initial)),
        "buy_fees_yuan":str(buy_fees),
        "sell_fees_yuan":str(sell_fees),
        "modeled_net_stop_loss_yuan":str(modeled_loss),
        "risk_denominator":"POSITION_BUY_NOTIONAL_NOT_ACCOUNT_EQUITY",
        "position_three_percent_risk_cap_yuan":str(position_risk_cap),
        "old_account_three_percent_cap_for_comparison_only_yuan":str(account_cap),
        "within_position_three_percent_stop_budget":within_risk,
        "within_cash_budget":within_cash,
        "synthetic_policy_pass":within_risk and within_cash,
        "actual_fill_evidence":False,
        "risk_limit_guaranteed_against_gaps_or_halts":False,
        "full_market_history_verified":False,
        "p4_out_of_sample_performance_validated":False,
        "v2_2_validated":False,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
        "paid_api_calls":0,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    scenario=json.loads(Path(args.input).read_text(encoding="utf-8"))
    receipt=check(scenario)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=="__main__":
    main()
