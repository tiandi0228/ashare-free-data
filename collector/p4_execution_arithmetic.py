"""P4 deterministic A-share execution arithmetic; research only, NO ORDERS."""
from decimal import Decimal, ROUND_HALF_UP

D=Decimal
def money(x):
    return D(str(x)).quantize(D("0.01"),rounding=ROUND_HALF_UP)

def replay(*,buy_price,sell_price,shares,buy_day,sell_day,commission_rate="0.0002854",commission_min="5",stamp_tax_rate="0.0005",transfer_rate="0.00001",slippage_buy="0",slippage_sell="0",risk_budget_fraction="0.03",planned_stop_price=None):
    from datetime import date
    if type(shares) is not int or shares<=0 or shares%100:
        raise ValueError("A-share mainboard purchase lot must be positive and divisible by 100")
    bd=date.fromisoformat(buy_day);sd=date.fromisoformat(sell_day)
    if sd<=bd:raise ValueError("T+1 forbids a same-day or earlier exit")
    buy_slippage=D(str(slippage_buy));sell_slippage=D(str(slippage_sell))
    if not all(v.is_finite() for v in (D(str(buy_price)),D(str(sell_price)),buy_slippage,sell_slippage)):
        raise ValueError("nonfinite prices or slippage")
    if buy_slippage<0 or sell_slippage<0:raise ValueError("negative slippage would create fictional improvement")
    bp=D(str(buy_price))+buy_slippage
    sp=D(str(sell_price))-sell_slippage
    if min(bp,sp)<=0:raise ValueError("prices after slippage must be positive")
    rate=D(str(commission_rate));floor=D(str(commission_min))
    tax=D(str(stamp_tax_rate));transfer=D(str(transfer_rate))
    budget=D(str(risk_budget_fraction))
    if not all(v.is_finite() for v in (rate,floor,tax,transfer,budget)) or any(x<0 for x in (rate,floor,tax,transfer)) or not D("0")<budget<=D("0.03"):
        raise ValueError("invalid cost or risk assumptions")
    gross_buy=bp*shares;gross_sell=sp*shares
    bc=money(max(floor,gross_buy*rate));sc=money(max(floor,gross_sell*rate))
    bt=money(gross_buy*transfer);st=money(gross_sell*transfer)
    sell_tax=money(gross_sell*tax)
    actual_buy=money(gross_buy+bc+bt)
    actual_sell=money(gross_sell-sc-st-sell_tax)
    pnl=money(actual_sell-actual_buy)
    planned_stop_risk=None
    if planned_stop_price is not None:
        stop=D(str(planned_stop_price))
        if not stop.is_finite() or stop<=0 or stop>=bp:
            raise ValueError("invalid planned stop quote")
        stop_fill=stop-sell_slippage
        if stop_fill<=0:raise ValueError("nonpositive stop scenario fill")
        stop_gross=stop_fill*shares
        stop_net=money(stop_gross-money(max(floor,stop_gross*rate))-money(stop_gross*transfer)-money(stop_gross*tax))
        stop_loss=money(max(D("0"),actual_buy-stop_net))
        planned_stop_risk={"scenario_net_loss":str(stop_loss),"scenario_within_budget":stop_loss<=gross_buy*budget,"stop_fill_verified":False,"gap_or_limit_down_covered":False}
    return {"phase":"P4_DETERMINISTIC_EXECUTION_UNIT","buy_day":buy_day,"sell_day":sell_day,
            "shares":shares,"buy_cost":str(actual_buy),"sell_proceeds":str(actual_sell),
            "net_pnl":str(pnl),"net_return_on_fill_notional":str((pnl/gross_buy).quantize(D("0.000001"))),
            "loss_fraction_on_fill_notional":str((max(D("0"),-pnl)/gross_buy).quantize(D("0.000001"))),
            "risk_budget_fraction":str(budget),"within_loss_budget":max(D("0"),-pnl)<=gross_buy*budget,
            "planned_stop_risk_scenario":planned_stop_risk,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "historical_OOS_validated":False}
