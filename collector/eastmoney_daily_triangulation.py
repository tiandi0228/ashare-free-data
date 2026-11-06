"""Two-symbol Eastmoney fqt=0 daily source observation vs archived Tencent/Baostock.

Explicitly bounded research, no source substitution, no P1 progress change.
Vendor and original receipt provenance are preserved. The third vendor is
independent from Tencent/Baostock in interface, not officially certified.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen

from collector.tencent_eight_sample_pilot import MINUTE_SYMBOLS
from collector.tencent_m5_extrema_forensics import forensic

HOST="https://push2his.eastmoney.com/api/qt/stock/kline/get"
FIELDS1="f1,f2,f3,f4,f5,f6"
FIELDS2="f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
MAX_BYTES=256*1024

def source_url(symbol):
    if symbol not in MINUTE_SYMBOLS:
        raise ValueError("only two approved mainboard symbols")
    market="1" if symbol.startswith("sh") else "0"
    return (f"{HOST}?secid={market}.{symbol[2:]}&fields1={FIELDS1}"
            f"&fields2={FIELDS2}&klt=101&fqt=0&end=20261106&lmt=12")

def price(value):
    try: d=Decimal(value)
    except (InvalidOperation,TypeError) as exc: raise ValueError("invalid provider price") from exc
    if not d.is_finite() or d<=0:raise ValueError("nonpositive daily price")
    return d

def parse(raw,symbol):
    source_url(symbol)
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:
        raise ValueError("bad response bytes")
    try:body=json.loads(raw.decode("utf-8","strict"))
    except (UnicodeError,ValueError) as exc:raise ValueError("not JSON") from exc
    market=1 if symbol.startswith("sh") else 0
    entry=body.get("data") if isinstance(body,dict) and body.get("rc")==0 else None
    if (not isinstance(entry,dict) or entry.get("code")!=symbol[2:]
            or entry.get("market")!=market):
        raise ValueError("unverified exact provider issuer")
    rows=entry.get("klines")
    if not isinstance(rows,list) or not 1<=len(rows)<=12:
        raise ValueError("missing bounded daily rows")
    out={}
    last=""
    for row in rows:
        if not isinstance(row,str):raise ValueError("unexpected kline row")
        cols=row.split(",")
        if len(cols)<6:raise ValueError("short daily row")
        day=cols[0]
        try:
            normalized=datetime.strptime(day,"%Y-%m-%d").date().isoformat()
        except ValueError as exc:raise ValueError("invalid provider day") from exc
        if day!=normalized or day<=last or day>"2026-11-06":
            raise ValueError("unsorted/out of scope provider date")
        last=day
        op,cl,hi,lo=(price(x) for x in cols[1:5])
        if lo>min(op,cl) or hi<max(op,cl) or lo>hi:
            raise ValueError("bad daily OHLC")
        out[day]={"open":str(op),"high":str(hi),"low":str(lo),"close":str(cl)}
    return out

def fetch(symbol):
    req=Request(source_url(symbol),headers={
        "User-Agent":"StockMate-Research-Source-Comparison/1.0",
        "Accept":"application/json","Referer":"https://quote.eastmoney.com/"})
    with urlopen(req,timeout=8) as response:
        if response.status!=200:raise ValueError("provider HTTP status")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("oversized provider response")
    return raw

def observe(root, transport=fetch):
    root=Path(root)
    if root.exists():raise ValueError("immutable output directory already exists")
    root.mkdir(parents=True)
    outcomes={}
    for symbol in MINUTE_SYMBOLS:
        folder=root/symbol
        folder.mkdir()
        receipt={"symbol":symbol,"url":source_url(symbol),
                 "status":"FAILED_UNVERIFIED","fqt":0,
                 "observed_at_utc":datetime.now(timezone.utc).isoformat(),
                 "historical_PIT_verified":False,"trade_gate":"BLOCKED",
                 "orders":[],"executable_candidates":[]}
        try:
            raw=transport(symbol)
            if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:
                raise ValueError("invalid source bytes")
            (folder/"source.bin").write_bytes(raw)
            receipt.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            bars=parse(raw,symbol)
            (folder/"daily.json").write_text(json.dumps(bars,indent=2)+"\n")
            receipt.update(status="OBSERVED_UNVERIFIED",days=len(bars),first=min(bars),last=max(bars))
            outcomes[symbol]=bars
        except (OSError,ValueError,TypeError,UnicodeError) as exc:
            receipt.update(error_type=type(exc).__name__,error_detail=str(exc)[:160])
        (folder/"quality.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    return outcomes

def triangulate(tencent_root, baostock_root, eastmoney_root):
    previous=forensic(tencent_root,baostock_root)
    east={}
    for symbol in MINUTE_SYMBOLS:
        folder=Path(eastmoney_root)/symbol
        receipt=json.loads((folder/"quality.json").read_text())
        if receipt.get("trade_gate")!="BLOCKED" or receipt.get("historical_PIT_verified") is not False:
            raise ValueError("unsafe vendor receipt")
        if receipt.get("status")!="OBSERVED_UNVERIFIED":
            east[symbol]=None
            continue
        raw=(folder/"source.bin").read_bytes()
        if hashlib.sha256(raw).hexdigest()!=receipt.get("sha256"):
            raise ValueError("source receipt SHA mismatch")
        parsed=parse(raw,symbol)
        if parsed!=json.loads((folder/"daily.json").read_text()):
            raise ValueError("vendor normalized rows differ from original")
        east[symbol]=parsed
    records=[]
    for o in previous["observations"]:
        symbol,day=o["symbol"],o["day"]
        e=(east[symbol] or {}).get(day)
        item={"symbol":symbol,"day":day,"prior_m5_mismatch":
             not o["same_day_ohlc_agrees_within_1_tick"],
              "status":"NO_EASTMONEY_DAILY_MATCH" if not e else "OBSERVED_UNVERIFIED"}
        if e:
            diffs={}
            for field in ("high","low"):
                m5=Decimal(o[field+"_observed_value"])
                b=m5-Decimal(o[field+"_difference_cn_yuan"])
                em=Decimal(e[field])
                diffs[field]={
                    "eastmoney_minus_baostock":str(em-b),
                    "eastmoney_minus_tencent_m5":str(em-m5),
                    "eastmoney_agrees_baostock_within_cent":abs(em-b)<=Decimal("0.01"),
                    "eastmoney_agrees_m5_within_cent":abs(em-m5)<=Decimal("0.01")
                }
            item["extrema"]=diffs
        records.append(item)
    return {"phase":"EASTMONEY_FQT0_TENCENT_M5_BAOSTOCK_DAILY_TRIANGULATION",
        "status":"OBSERVED_RESEARCH_ONLY" if all(east.values()) else "PARTIAL_SOURCE_UNAVAILABLE",
        "previous_comparable_days":previous["comparable_days"],
        "previous_mismatch_days":previous["mismatch_days"],
        "records":records,"eastmoney_days":{s:len(east[s] or {}) for s in MINUTE_SYMBOLS},
        "root_cause_confirmed":False,
        "auction_inclusion_confirmed":False,
        "official_exchange_authenticated":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--tencent",required=True,type=Path)
    p.add_argument("--baostock",required=True,type=Path)
    p.add_argument("--live",action="store_true")
    args=p.parse_args()
    if not args.live:p.error("explicit --live needed for bounded public source request")
    observe(args.out)
    report=triangulate(args.tencent,args.baostock,args.out)
    (args.out/"comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()
