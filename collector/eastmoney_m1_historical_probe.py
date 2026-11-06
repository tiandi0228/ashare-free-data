"""One-shot bounded Eastmoney historical 1m date-selectability research probe.

Two symbols × two explicit historical dates; four HTTP requests maximum.
This is an observational probe, not evidence of full-day completeness unless
exact expected minute labels exist. No retries, orders, schedules or trades.
"""
import argparse
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen

SYMBOLS=("sh600519","sz002249")
DAYS=("2026-11-02","2026-11-05")
HOST="54.push2his.eastmoney.com"
MAX_BYTES=512*1024


def url(symbol,day):
    if symbol not in SYMBOLS or day not in DAYS:
        raise ValueError("sample not on approved allowlist")
    d=day.replace("-","")
    market="1" if symbol.startswith("sh") else "0"
    return (f"https://{HOST}/api/qt/stock/kline/get?secid={market}.{symbol[2:]}"
      "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
      f"&klt=1&fqt=0&beg={d}&end={d}&lmt=300")


def expected(day):
    d=day.replace("-","")
    return {d+f"{h:02d}{m:02d}" for h,a,b in
            ((9,31,59),(10,0,59),(11,0,30),(13,1,59),(14,0,59),(15,0,0))
            for m in range(a,b+1)}


def number(v):
    try:x=Decimal(v)
    except (InvalidOperation,TypeError) as ex:raise ValueError("bad decimal") from ex
    if not x.is_finite() or x<=0:raise ValueError("bad price")
    return x


def parse(raw,symbol,day):
    url(symbol,day)
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:
        raise ValueError("invalid raw response size")
    try:j=json.loads(raw.decode("utf-8"))
    except (ValueError,UnicodeError) as ex:raise ValueError("invalid JSON") from ex
    market=1 if symbol.startswith("sh") else 0
    node=j.get("data") if isinstance(j,dict) and j.get("rc")==0 else None
    if not isinstance(node,dict) or node.get("code")!=symbol[2:] or node.get("market")!=market:
        raise ValueError("unexpected issuer or vendor failure")
    vals=node.get("klines")
    if not isinstance(vals,list) or len(vals)>300:raise ValueError("missing or too many bars")
    rows=[]
    prev=None
    for row in vals:
        if not isinstance(row,str):raise ValueError("bad minute record")
        f=row.split(",")
        if len(f)<5:raise ValueError("short minute record")
        timestamp=f[0]
        try: t=datetime.strptime(timestamp,"%Y-%m-%d %H:%M")
        except ValueError as ex:raise ValueError("invalid time") from ex
        if prev is not None and t<=prev:raise ValueError("unordered/duplicate bars")
        prev=t
        o,c,h,l=map(number,f[1:5])
        if l>min(o,c) or h<max(o,c) or h<l:raise ValueError("invalid OHLC")
        rows.append({"timestamp_cn":t.strftime("%Y%m%d%H%M"),
                     "open":str(o),"close":str(c),"high":str(h),"low":str(l)})
    wanted=expected(day)
    observed={x["timestamp_cn"] for x in rows}
    target=[x for x in rows if x["timestamp_cn"][:8]==day.replace("-","")]
    full=(len(rows)==240 and len(target)==240 and observed==wanted)
    return {"symbol":symbol,"requested_day":day,
        "provider_rows":len(rows),"target_day_rows":len(target),
        "unexpected_day_rows":len(rows)-len(target),
        "expected_day_rows":240,"missing_minute_labels":len(wanted-observed),
        "full_requested_day_coverage":full,
        "first":rows[0]["timestamp_cn"] if rows else None,
        "last":rows[-1]["timestamp_cn"] if rows else None,
        "status":"FULL_DAY_UNVERIFIED" if full else "NOT_FULL_DAY",
        "day_extrema":({
            "high":str(max(Decimal(x["high"]) for x in target)),
            "low":str(min(Decimal(x["low"]) for x in target)),
        } if full else None)}


def request(symbol,day):
    req=Request(url(symbol,day),headers={"User-Agent":"StockMate-Date-Scoped-Research/1.0",
         "Accept":"application/json","Referer":"https://quote.eastmoney.com/"})
    with urlopen(req,timeout=8) as res:
        if res.status!=200:raise ValueError("HTTP status")
        raw=res.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError("response too large")
    return raw


def run(out,transport=request):
    root=Path(out)
    if root.exists():raise ValueError("immutable destination already exists")
    root.mkdir(parents=True)
    reports=[]
    for symbol in SYMBOLS:
        for day in DAYS:
            folder=root/(symbol+"_"+day)
            folder.mkdir()
            item={"symbol":symbol,"day":day,"url":url(symbol,day),
                  "status":"FAILED_UNVERIFIED","trade_gate":"BLOCKED",
                  "historical_PIT_verified":False,"orders":[],"executable_candidates":[]}
            try:
                raw=transport(symbol,day)
                if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError("invalid bytes")
                (folder/"source.bin").write_bytes(raw)
                item["sha256"]=hashlib.sha256(raw).hexdigest()
                item["bytes"]=len(raw)
                observation=parse(raw,symbol,day)
                item.update(observation)
                (folder/"observation.json").write_text(json.dumps(observation,ensure_ascii=False,indent=2)+"\n")
            except (OSError,TypeError,ValueError,UnicodeError) as ex:
                item["error_type"]=type(ex).__name__
                item["error_detail"]=str(ex)[:140]
            (folder/"quality.json").write_text(json.dumps(item,ensure_ascii=False,indent=2)+"\n")
            reports.append(item)
    summary={"phase":"EASTMONEY_DATE_SCOPED_M1_FOUR_REQUEST_RESEARCH",
        "request_count":4,"full_days":sum(x["status"]=="FULL_DAY_UNVERIFIED" for x in reports),
        "results":reports,"historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[]}
    (root/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--live",action="store_true")
    a=p.parse_args()
    if not a.live:p.error("network disabled without explicit --live")
    print(json.dumps(run(a.out),ensure_ascii=False))


if __name__=="__main__":main()
