"""Research-only aggregation of receipt-observed partial fills and T+1 inventory."""
from decimal import Decimal,ROUND_HALF_UP
from datetime import date
from collector.p4_limit_order_replay import replay as order_replay
D=Decimal
def cents(x):return x.quantize(D("0.01"),rounding=ROUND_HALF_UP)
def summarize(*,buy_order,sell_order=None,commission_rate="0.0002854",commission_min="5",stamp_tax_rate="0.0005",transfer_rate="0.00001"):
    b=order_replay(**buy_order)
    if b["side"]!="BUY":raise ValueError("buy leg required")
    quantities=[e["shares"] for e in buy_order["events"] if e["kind"]=="FILL_RECEIPT"]
    if b["receipt_fill_shares"]!=sum(quantities):raise ValueError("inconsistent receipts")
    rate,floor,tax,transfer=map(D,(commission_rate,commission_min,stamp_tax_rate,transfer_rate))
    if not all(v.is_finite() and v>=0 for v in (rate,floor,tax,transfer)):raise ValueError("invalid rates")
    if not quantities and sell_order is not None:raise ValueError("no evidence of purchased shares")
    # Commission charged once for each order-side aggregate, not once per partial fill.
    gross_buy=D(b["notional_observed"])
    buy_fees=cents(max(floor,gross_buy*rate))+cents(gross_buy*transfer) if quantities else D("0")
    result={"phase":"P4_V22_PARTIAL_FILL_FEE_AND_INVENTORY_RESEARCH",
            "observed_buy_shares":b["receipt_fill_shares"],"buy_gross":str(cents(gross_buy)),
            "buy_fees_model":str(buy_fees),"observed_sell_shares":0,
            "sell_fees_model":"0.00","inventory_shares":b["receipt_fill_shares"],
            "fee_model_unverified":True,"receipt_fill_certified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    if sell_order is not None:
        s=order_replay(**sell_order)
        if s["side"]!="SELL":raise ValueError("sell leg required")
        buy_days=[date.fromisoformat(e["observed_at"][:10]) for e in buy_order["events"] if e["kind"]=="FILL_RECEIPT"]
        for e in sell_order["events"]:
            if e["kind"]=="FILL_RECEIPT":
                sold_on=date.fromisoformat(e["observed_at"][:10])
                available=sum(x["shares"] for x in buy_order["events"] if x["kind"]=="FILL_RECEIPT" and date.fromisoformat(x["observed_at"][:10])<sold_on)
                already_sold=sum(x["shares"] for x in sell_order["events"] if x["kind"]=="FILL_RECEIPT" and x["observed_at"]<=e["observed_at"])
                if already_sold>available:raise ValueError("T+1 available inventory exceeded")
        if s["receipt_fill_shares"]>b["receipt_fill_shares"]:raise ValueError("oversold")
        gross_sell=D(s["notional_observed"])
        sell_fees=cents(max(floor,gross_sell*rate))+cents(gross_sell*transfer)+cents(gross_sell*tax) if s["receipt_fill_shares"] else D("0")
        result.update(observed_sell_shares=s["receipt_fill_shares"],sell_fees_model=str(sell_fees),
                      inventory_shares=b["receipt_fill_shares"]-s["receipt_fill_shares"])
    return result
