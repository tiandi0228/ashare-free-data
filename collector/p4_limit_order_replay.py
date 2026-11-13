"""Evidence-bound V2.2 limit-order partial fill and cancellation arithmetic; NO ORDERS."""
from decimal import Decimal,InvalidOperation
from datetime import datetime

def parse_time(t):
    d=datetime.fromisoformat(t.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:raise ValueError("timezone required")
    return d
def replay(*,side,order_shares,limit_price,placed_at,expires_at,events):
    if side not in ("BUY","SELL"):raise ValueError("invalid side")
    if type(order_shares) is not int or order_shares<=0 or (side=="BUY" and order_shares%100):
        raise ValueError("buy quantities require board lots of 100")
    limit=Decimal(str(limit_price))
    if not limit.is_finite() or limit<=0:raise ValueError("invalid limit")
    start=parse_time(placed_at);expiry=parse_time(expires_at)
    if expiry<=start:raise ValueError("invalid expiry")
    if not isinstance(events,list):raise ValueError("events must be explicit observations")
    filled=0;notional=Decimal("0");closed=False;cancelled=False;last=start
    records=[]
    seen_receipts=set()
    for event in events:
        timestamp=parse_time(event["observed_at"])
        if timestamp<last or timestamp>expiry or closed:raise ValueError("invalid event chronology")
        last=timestamp
        action=event["kind"]
        if action not in ("FILL_RECEIPT", "CANCEL_RECEIPT"):
            raise ValueError("unknown event")
        sha=event.get("source_sha256")
        if not isinstance(sha,str) or len(sha)!=64 or any(x not in "0123456789abcdef" for x in sha):
            raise ValueError("missing independently observable event receipt")
        # The replay schema has no row ID within a receipt. Refuse ambiguous
        # reuse rather than treating copied bytes as another event.
        if sha in seen_receipts:
            raise ValueError("duplicate event receipt digest")
        seen_receipts.add(sha)
        if action=="FILL_RECEIPT":
            qty=event["shares"];price=Decimal(str(event["price"]))
            if (type(qty) is not int or qty<=0 or filled+qty>order_shares
                or not price.is_finite() or price<=0
                or (side=="BUY" and price>limit) or (side=="SELL" and price<limit)):
                raise ValueError("invalid limit or fill receipt")
            filled+=qty;notional+=price*qty
            if filled==order_shares:closed=True
            records.append({"kind":"EVIDENCED_FILL_UNVERIFIED","shares":qty,"source_sha256":sha})
        elif action=="CANCEL_RECEIPT":
            cancelled=True;closed=True
            records.append({"kind":"EVIDENCED_CANCEL_UNVERIFIED","source_sha256":sha})
    remainder=order_shares-filled
    return {"phase":"P4_V22_LIMIT_ORDER_RESEARCH_REPLAY","side":side,
            "requested_shares":order_shares,"receipt_fill_shares":filled,
            "unfilled_shares":remainder,"notional_observed":str(notional),
            "weighted_fill_price":str(notional/filled) if filled else None,
            "cancel_receipt_present":cancelled,"terminal_state":("CANCELLED_PARTIAL" if filled else "CANCELLED_UNFILLED") if cancelled else ("FILLED_RECEIPTS_PRESENT" if not remainder else "PARTIAL_RECEIPTS_PRESENT" if filled else "UNFILLED_PENDING_OR_EXPIRED"),
            "evidence_records":records,"real_fill_certified":False,
            "fees_finalized":False,"historical_OOS_validated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
