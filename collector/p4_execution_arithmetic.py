"""P4 deterministic A-share execution arithmetic; research only, NO ORDERS."""
from decimal import Decimal, ROUND_HALF_UP

D=Decimal
def money(x):
    return D(str(x)).quantize(D("0.01"),rounding=ROUND_HALF_UP)

def replay(*,buy_price,sell_price,shares,buy_day,sell_day,commission_rate="0.0002854",commission_min="5",stamp_tax_rate="0.0005",transfer_rate="0.00001",slippage_buy="0",slippage_sell="0",risk_budget_fraction="0.03"):
    from datetime import date
    if type(shares) is not int or shares<=0 or shares%100:
        raise ValueError("A-share mainboard purchase lot must be positive and divisible by 100")
    bd=date.fromisoformat(buy_day);sd=date.fromisoformat(sell_day)
    if sd<=bd:raise ValueError("T+1 forbids a same-day or earlier exit")
    bp=D(str(buy_price))+D(str(slippage_buy))
    sp=D(str(sell_price))-D(str(slippage_sell))
    if min(bp,sp)<=0:raise ValueError("prices after slippage must be positive")
    rate=D(str(commission_rate));floor=D(str(commission_min))
    tax=D(str(stamp_tax_rate));transfer=D(str(transfer_rate))
    budget=D(str(risk_budget_fraction))
    if any(x<0 for x in (rate,floor,tax,transfer)) or not D("0")<budget<=D("0.03"):
        raise ValueError("invalid cost or risk assumptions")
    gross_buy=bp*shares;gross_sell=sp*shares
    bc=money(max(floor,gross_buy*rate));sc=money(max(floor,gross_sell*rate))
    bt=money(gross_buy*transfer);st=money(gross_sell*transfer)
    sell_tax=money(gross_sell*tax)
    actual_buy=money(gross_buy+bc+bt)
    actual_sell=money(gross_sell-sc-st-sell_tax)
    pnl=money(actual_sell-actual_buy)
    return {"phase":"P4_DETERMINISTIC_EXECUTION_UNIT","buy_day":buy_day,"sell_day":sell_day,
            "shares":shares,"buy_cost":str(actual_buy),"sell_proceeds":str(actual_sell),
            "net_pnl":str(pnl),"net_return_on_fill_notional":str((pnl/gross_buy).quantize(D("0.000001"))),
            "loss_fraction_on_fill_notional":str((max(D("0"),-pnl)/gross_buy).quantize(D("0.000001"))),
            "risk_budget_fraction":str(budget),"within_loss_budget":max(D("0"),-pnl)<=gross_buy*budget,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "historical_OOS_validated":False}
