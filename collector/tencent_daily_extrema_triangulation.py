"""Bounded, opt-in Tencent unadjusted daily K research probe and triangulation.

Two provider requests at most; no retries, no cron, no orders. Reuses existing
Tencent m5 and Baostock artifacts. A same-vendor daily/m5 agreement is NOT an
independent confirmation of daily extremes or auction inclusion.
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
from collector.p0_tencent_quote_probe import SYMBOL

URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param="
MAX_BYTES = 512 * 1024

def source_url(symbol):
    if not isinstance(symbol,str) or not SYMBOL.fullmatch(symbol) or symbol not in MINUTE_SYMBOLS:
        raise ValueError("only two preapproved SH/SZ mainboard symbols")
    return f"{URL}{symbol},day,,,240,qfq"

def amount(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)) or not str(value).strip():
        raise ValueError("bad numeric")
    try: d=Decimal(str(value))
    except InvalidOperation as exc: raise ValueError("bad decimal") from exc
    if not d.is_finite():raise ValueError("nonfinite decimal")
    return d

def parse(raw,symbol):
    source_url(symbol)
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:
        raise ValueError("invalid response size")
    try: body=json.loads(raw.decode("utf-8","strict"))
    except (UnicodeError,ValueError) as exc: raise ValueError("invalid JSON") from exc
    data=body.get("data") if isinstance(body,dict) and body.get("code")==0 else None
    entry=data.get(symbol) if isinstance(data,dict) else None
    if not isinstance(entry,dict):raise ValueError("missing exact symbol")
    # NEVER substitute qfqday for day. The raw day feed must be present.
    bars=entry.get("day")
    if not isinstance(bars,list) or not 1<=len(bars)<=240:
        raise ValueError("missing unadjusted daily entries")
    result={}
    prior=""
    for row in bars:
        if not isinstance(row,list) or len(row)<6:raise ValueError("invalid vendor daily schema")
        day=row[0]
        try:
            if not isinstance(day,str):
                raise ValueError("invalid date")
            d=datetime.strptime(day,"%Y-%m-%d").date().isoformat()
            if d!=day or d<=prior:raise ValueError("unordered vendor days")
        except (ValueError,TypeError) as exc:
            raise ValueError("invalid vendor daily date") from exc
        prior=d
        op,cl,hi,lo=map(amount,row[1:5])
        if min(op,cl,hi,lo)<=0 or lo>min(op,cl) or hi<max(op,cl):
            raise ValueError("bad unadjusted OHLC")
        result[day]={k:str(v) for k,v in zip(("open","close","high","low"),(op,cl,hi,lo))}
    return result

def fetch(symbol):
    req=Request(source_url(symbol),headers={"User-Agent":"StockMate-Research-Daily-Triangulation/1.0",
                                            "Accept":"application/json"})
    with urlopen(req,timeout=8) as resp:
        if resp.status!=200:raise ValueError("HTTP unsuccessful")
        raw=resp.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("oversized response")
    return raw

def capture(out,transport=fetch):
    root=Path(out)
    if root.exists():raise ValueError("immutable evidence directory already exists")
    root.mkdir(parents=True)
    results={}
    for sym in MINUTE_SYMBOLS:
        dest=root/sym
        dest.mkdir()
        receipt={"symbol":sym,"url":source_url(sym),"status":"FAILED_UNVERIFIED",
                 "captured_at_utc":datetime.now(timezone.utc).isoformat(),
                 "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[]}
        try:
            raw=transport(sym)
            if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError("unbounded bytes")
            (dest/"raw.bin").write_bytes(raw)
            receipt["sha256"]=hashlib.sha256(raw).hexdigest()
            data=parse(raw,sym)
            (dest/"daily.json").write_text(json.dumps(data,indent=2)+"\n")
            receipt.update(status="OBSERVED_UNVERIFIED",days=len(data),
                           first=min(data),last=max(data),bytes=len(raw))
            results[sym]=data
        except (OSError,ValueError,TypeError,UnicodeError) as exc:
            receipt.update(error_type=type(exc).__name__,error_detail=str(exc)[:120])
        (dest/"quality.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return results

def triangulate(original_tencent,original_baostock,daily_root):
    old=forensic(original_tencent,original_baostock)
    daily={}
    for sym in MINUTE_SYMBOLS:
        folder=Path(daily_root)/sym
        receipt=json.loads((folder/"quality.json").read_text())
        if receipt.get("status")!="OBSERVED_UNVERIFIED":
            daily[sym]=None
            continue
        raw=(folder/"raw.bin").read_bytes()
        if hashlib.sha256(raw).hexdigest()!=receipt["sha256"]:
            raise ValueError("Tencent daily source SHA mismatch")
        parsed=parse(raw,sym)
        if parsed!=json.loads((folder/"daily.json").read_text()):
            raise ValueError("Tencent daily source rows tampered")
        daily[sym]=parsed
    comparisons=[]
    for item in old["observations"]:
        sym,day=item["symbol"],item["day"]
        d=(daily[sym] or {}).get(day)
        outcome={"symbol":sym,"day":day,"previous_m5_disagreement":
            not item["same_day_ohlc_agrees_within_1_tick"],
            "state":"NO_UNADJUSTED_TENCENT_DAILY_DAY" if not d else "TRIANGULATED_RESEARCH_ONLY"}
        if d:
            diffs={}
            verdict={}
            for field in ("open","high","low","close"):
                a=Decimal(d[field])
                m=Decimal(item["price_differences_tencent_minus_baostock"][field])
                # Recover Baostock daily by subtracting reported m5 differences
                # from the corresponding m5 aggregated prices, using original
                # extreme observations where needed.
                if field in ("low","high"):
                    m5=Decimal(item[field+"_observed_value"])
                    b=m5-m
                    verdict[field]={
                        "tencent_daily_minus_baostock":str(a-b),
                        "tencent_daily_minus_m5":str(a-m5),
                    }
                else:
                    # This audit deliberately limits numeric attribution to
                    # extremes, for which the m5 original is bound in forensic.
                    verdict[field]={"comparison":"NOT_REPLAYED_IN_THIS_DIAGNOSTIC"}
            outcome["extrema"]=verdict
            outcome["daily_matches_baostock_extrema"]=all(
                abs(Decimal(verdict[f]["tencent_daily_minus_baostock"]))<=Decimal("0.01")
                for f in ("high","low"))
        comparisons.append(outcome)
    return {"phase":"TENCENT_DAILY_M5_BAOSTOCK_EXTREMA_TRIANGULATION",
            "status":"RESEARCH_TRIANGULATION_UNVERIFIED",
            "comparisons":comparisons,
            "comparable_prior_days":old["comparable_days"],
            "daily_vendor_days_observed":{s:len(d or {}) for s,d in daily.items()},
            "independent_source_consistency_certified":False,
            "auction_root_cause_confirmed":False,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--tencent-archive",type=Path,required=True)
    a.add_argument("--baostock-archive",type=Path,required=True)
    a.add_argument("--live",action="store_true")
    x=a.parse_args()
    if not x.live:a.error("explicit --live required for vendor access")
    capture(x.out)
    result=triangulate(x.tencent_archive,x.baostock_archive,x.out)
    (x.out/"triangulation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__": main()
