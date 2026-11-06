"""Two-issuer research-only Tencent m5 versus Baostock daily OHLC comparison.

Reads already-archived original Tencent bytes (with SHA revalidation), fetches
a bounded two-issuer *unadjusted* daily Baostock observation only when explicitly
requested. Excludes incomplete trading days. Never equates close to an executable
quote or certifies volume units, PIT membership or trading.
"""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from collector import p1_tencent_minute_probe as minute
from collector.tencent_eight_sample_pilot import MINUTE_SYMBOLS, PERIODS
from collector.tencent_archived_minute_audit import replay

FIELDS = "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus".split(",")
START, END = "2026-10-30", "2026-11-06"


def expected_m5_labels(day):
    prefix = day.replace("-", "")
    return {f"{prefix}{hour:02d}{minute:02d}"
            for hour, begin, finish in ((9,35,55),(10,0,55),(11,0,30),
                                        (13,5,55),(14,0,55),(15,0,0))
            for minute in range(begin,finish+1,5)}


def utcday_groups(raw, symbol):
    rows=minute.parse(raw,symbol,"m5")
    grouped=defaultdict(list)
    for row in rows:
        day=datetime.strptime(row["timestamp_cn"],"%Y%m%d%H%M").date().isoformat()
        grouped[day].append(row)
    result={}
    for day,bars in grouped.items():
        labels={x["timestamp_cn"] for x in bars}
        expected=expected_m5_labels(day)
        # A complete day must exactly cover the 48 canonical ending labels.
        # Suspensions, delayed bars, atypical closing labels remain excluded.
        if labels != expected or len(bars) != len(expected):
            result[day]={"status":"INCOMPLETE_OR_NONCANONICAL_SESSION",
                         "observed":len(bars),"missing_labels":len(expected-labels),
                         "unexpected_labels":len(labels-expected)}
            continue
        value=lambda x: Decimal(str(x))
        result[day]={"status":"COMPLETE_OBSERVED_M5_LABELS",
                     "observed":len(bars),
                     "open":str(value(bars[0]["open"])),
                     "high":str(max(value(b["high"]) for b in bars)),
                     "low":str(min(value(b["low"]) for b in bars)),
                     "close":str(value(bars[-1]["close"]))}
    return result


def read_original_tencent(root):
    root=Path(root)
    checks=replay(root)  # verifies all 11 source responses and recorded digests
    if not checks["source_sha256_reverified"]:
        raise ValueError("source archive not verified")
    result={}
    for sym in MINUTE_SYMBOLS:
        i=1+MINUTE_SYMBOLS.index(sym)*len(PERIODS)+PERIODS.index("m5")
        folder=root/f"{i:02d}_{sym}_m5"
        result[sym]=utcday_groups((folder/"response.bin").read_bytes(),sym)
    return result


def parse_baostock(rows,symbol):
    expected=symbol[:2]+"."+symbol[2:]
    parsed={}
    for row in rows:
        if list(row.keys())!=FIELDS or row["code"]!=expected:
            raise ValueError("unrecognized Baostock daily bar schema or issuer")
        day=row["date"]
        if not START<=day<=END or day in parsed:
            raise ValueError("out-of-range or duplicate vendor day")
        if row["adjustflag"]!="3" or row["tradestatus"] not in ("0","1"):
            raise ValueError("Baostock adjustment/status not proven")
        if row["tradestatus"]=="1":
            try:
                prices=[Decimal(row[k]) for k in ("open","high","low","close")]
            except InvalidOperation as exc:
                raise ValueError("invalid Baostock decimal") from exc
            if any(not q.is_finite() or q<=0 for q in prices):
                raise ValueError("bad Baostock prices")
            if prices[1]<max(prices[0],prices[3]) or prices[2]>min(prices[0],prices[3]):
                raise ValueError("bad Baostock OHLC")
        parsed[day]=row
    return parsed


def compare(tencent, baostock, tolerance=Decimal("0.01")):
    if set(tencent)!=set(MINUTE_SYMBOLS) or set(baostock)!=set(MINUTE_SYMBOLS):
        raise ValueError("both source issuer IDs required")
    records=[]
    for sym in MINUTE_SYMBOLS:
        for day,daybar in sorted(tencent[sym].items()):
            item={"symbol":sym,"day":day,"tencent_status":daybar["status"],
                  "baostock_status":"MISSING"}
            if daybar["status"]!="COMPLETE_OBSERVED_M5_LABELS":
                item["comparison"]="NOT_COMPARABLE_INCOMPLETE_MINUTES"
            else:
                row=baostock[sym].get(day)
                if row is None:
                    item["comparison"]="NOT_COMPARABLE_MISSING_VENDOR_DAY"
                elif row["tradestatus"]!="1":
                    item["baostock_status"]="NON_TRADING"
                    item["comparison"]="NOT_COMPARABLE_NONTRADING"
                else:
                    item["baostock_status"]="ACTIVE_UNADJUSTED"
                    differences={}
                    for key in ("open","high","low","close"):
                        differences[key]=str(Decimal(daybar[key])-Decimal(row[key]))
                    item["differences_cny"]=differences
                    item["comparison"]="RESEARCH_OHLC_WITHIN_1_TICK" if all(
                        abs(Decimal(v))<=tolerance for v in differences.values()
                    ) else "RESEARCH_OHLC_DISAGREEMENT"
            records.append(item)
    comparable=sum(x["comparison"].startswith("RESEARCH_OHLC_") for x in records)
    equal=sum(x["comparison"]=="RESEARCH_OHLC_WITHIN_1_TICK" for x in records)
    return {"phase":"TENCENT_BAOSTOCK_COMPLETED_DAY_RESEARCH_COMPARISON",
            "status":"OBSERVED_DIFFERENCES_UNVERIFIED" if comparable else "NO_COMPARABLE_FULL_DAYS",
            "vendor_a":"Tencent archived m5 source",
            "vendor_b":"Baostock frequency=d adjustflag=3",
            "comparison_records":records,"comparable_days":comparable,
            "within_tick_days":equal,"disagreement_days":comparable-equal,
            "volume_comparison_performed":False,
            "independent_source_consistency_certified":False,
            "minute_bar_completion_certified":False,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}


def fetch_baostock(dest, bs):
    dest=Path(dest)
    if dest.exists():
        raise ValueError("Baostock evidence destination already exists")
    dest.mkdir(parents=True)
    result={}
    login=bs.login()
    if login.error_code!="0":
        raise ValueError("Baostock login unsuccessful")
    try:
        for symbol in MINUTE_SYMBOLS:
            code=symbol[:2]+"."+symbol[2:]
            response=bs.query_history_k_data_plus(
                code,fields=",".join(FIELDS),start_date=START,end_date=END,
                frequency="d",adjustflag="3")
            if response.error_code!="0" or list(response.fields)!=FIELDS:
                raise ValueError("Baostock error or schema mismatch")
            rows=[]
            while response.next():
                values=response.get_row_data()
                if len(values)!=len(FIELDS) or len(rows)>=20:
                    raise ValueError("Baostock rows over budget or malformed")
                rows.append(dict(zip(FIELDS,values)))
            if not rows:
                raise ValueError("Baostock returned no rows")
            data=(",".join(FIELDS)+"\n"+"".join(
                ",".join(row[field] for field in FIELDS)+"\n" for row in rows)).encode()
            path=dest/(symbol+".csv")
            path.write_bytes(data)
            result[symbol]=parse_baostock(rows,symbol)
            (dest/(symbol+".sha256")).write_text(hashlib.sha256(data).hexdigest()+"\n")
    finally:
        bs.logout()
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tencent-archive",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--live-baostock",action="store_true")
    a=p.parse_args()
    if not a.live_baostock:
        p.error("independent vendor request disabled by default")
    dest=a.out
    if dest.exists():p.error("destination must be new")
    import baostock as bs
    t=read_original_tencent(a.tencent_archive)
    daily=fetch_baostock(dest/"baostock_original",bs)
    output=compare(t,daily)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"comparison.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":output["status"],"comparable_days":output["comparable_days"],
                      "within_tick_days":output["within_tick_days"],
                      "disagreement_days":output["disagreement_days"],
                      "records":output["comparison_records"],
                      "trade_gate":output["trade_gate"]},ensure_ascii=False))


if __name__=="__main__":main()
