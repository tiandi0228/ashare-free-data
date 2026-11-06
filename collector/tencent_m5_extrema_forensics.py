"""Replay-only attribution of Tencent m5 high/low differences vs Baostock daily.

Requires original Tencent and Baostock artifacts. Does not network, impute,
make a market-source correction, or unlock trading. A trading-day price extreme
may be absent from these m5 rows (e.g. session boundary), but causation is not
asserted from that observation.
"""
import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from collector import p1_tencent_minute_probe as minute
from collector.tencent_baostock_daily_compare import (
    MINUTE_SYMBOLS, PERIODS, FIELDS, parse_baostock, compare, read_original_tencent
)

def _dec(value):
    d=Decimal(str(value))
    if not d.is_finite():
        raise ValueError("nonfinite price")
    return d

def _original_baostock(path,symbol):
    path=Path(path)/"baostock_original"
    raw=(path/(symbol+".csv")).read_bytes()
    expected=(path/(symbol+".sha256")).read_text(encoding="utf-8").strip()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError("Baostock original CSV SHA mismatch")
    text=raw.decode("utf-8",errors="strict")
    rows=list(csv.DictReader(text.splitlines()))
    if not rows or list(rows[0].keys())!=FIELDS:
        raise ValueError("unknown Baostock original schema")
    return parse_baostock(rows,symbol)

def _extreme(rows,key):
    values=[_dec(b[key]) for b in rows]
    val=min(values) if key=="low" else max(values)
    labels=[b["timestamp_cn"] for b in rows if _dec(b[key])==val]
    return str(val), labels

def attribute(tencent_bars, baostock_rows, symbol):
    by_day={}
    for row in tencent_bars:
        d=row["timestamp_cn"][:8]
        by_day.setdefault(d,[]).append(row)
    outcomes=[]
    for daystr, bars in sorted(by_day.items()):
        day=daystr[:4]+"-"+daystr[4:6]+"-"+daystr[6:]
        ref=baostock_rows.get(day)
        if ref is None or ref["tradestatus"]!="1":
            continue
        item={"symbol":symbol,"day":day,"observed_m5_rows":len(bars),
              "first_m5_label":bars[0]["timestamp_cn"],
              "last_m5_label":bars[-1]["timestamp_cn"]}
        differences={}
        for key in ("open","high","low","close"):
            if key=="open":
                actual=_dec(bars[0]["open"])
            elif key=="close":
                actual=_dec(bars[-1]["close"])
            else:
                actual=min(_dec(b[key]) for b in bars) if key=="low" else max(_dec(b[key]) for b in bars)
            expected=_dec(ref[key])
            differences[key]=str(actual-expected)
        item["price_differences_tencent_minus_baostock"]=differences
        for key in ("high","low"):
            actual,labels=_extreme(bars,key)
            item[key+"_observed_value"]=actual
            item[key+"_observed_at_cn"]=labels
            item[key+"_baostock_daily_value"]=ref[key]
            item[key+"_difference_cn_yuan"]=differences[key]
            item[key+"_match"]=abs(_dec(differences[key]))<=Decimal("0.01")
        item["same_day_ohlc_agrees_within_1_tick"]=all(
            abs(_dec(v))<=Decimal("0.01") for v in differences.values()
        )
        item["extreme_mismatch_hypotheses"]=[
            "AUCTION_OR_SESSION_BOUNDARY_NOT_ESTABLISHED",
            "PROVIDER_BAR_EXTREMA_SEMANTICS_NOT_ESTABLISHED",
            "VENDOR_CORRECTION_OR_DATA_DIFFERENCE_NOT_ESTABLISHED",
        ] if not (item["high_match"] and item["low_match"]) else []
        outcomes.append(item)
    return outcomes

def forensic(tencent_root,baostock_root):
    t=read_original_tencent(tencent_root)  # also verifies all 11 original Tencent receipts
    b={s:_original_baostock(baostock_root,s) for s in MINUTE_SYMBOLS}
    prior=compare(t,b)
    observations=[]
    for sym in MINUTE_SYMBOLS:
        i=1+MINUTE_SYMBOLS.index(sym)*len(PERIODS)+PERIODS.index("m5")
        raw=(Path(tencent_root)/f"{i:02d}_{sym}_m5"/"response.bin").read_bytes()
        observations += attribute(minute.parse(raw,sym,"m5"),b[sym],sym)
    comparable={ (x["symbol"],x["day"]) for x in prior["comparison_records"]
                if x["comparison"].startswith("RESEARCH_OHLC_")}
    matching={ (x["symbol"],x["day"]) for x in observations
              if x["same_day_ohlc_agrees_within_1_tick"]}
    # Only produce diagnosis for comparable, fully observed sessions.
    observations=[x for x in observations if (x["symbol"],x["day"]) in comparable]
    if len(observations)!=prior["comparable_days"]:
        raise ValueError("forensic comparable set mismatch")
    if len(matching & comparable)!=prior["within_tick_days"]:
        raise ValueError("forensic and previous comparison disagreed")
    mismatch=[x for x in observations if not x["same_day_ohlc_agrees_within_1_tick"]]
    return {
        "phase":"TENCENT_BAOSTOCK_M5_EXTREMA_FORENSIC_REPLAY",
        "status":"MISMATCHES_ATTRIBUTED_TO_FIELDS_NOT_ROOT_CAUSES" if mismatch
                  else "NO_MISMATCHES_IN_COMPARABLE_SAMPLE",
        "comparable_days":len(observations),
        "mismatch_days":len(mismatch),
        "mismatch_fields_count":{
            key:sum(abs(_dec(x["price_differences_tencent_minus_baostock"][key]))>Decimal("0.01")
                    for x in observations) for key in ("open","high","low","close")
        },
        "observations":observations,
        "root_cause_confirmed":False,
        "source_bytes_reverified":True,
        "cross_provider_correction_approved":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED", "orders":[],"executable_candidates":[],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tencent",required=True,type=Path)
    ap.add_argument("--baostock",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    data=forensic(a.tencent,a.baostock)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False))

if __name__=="__main__":
    main()
