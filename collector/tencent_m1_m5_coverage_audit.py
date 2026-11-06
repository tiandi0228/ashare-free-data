"""Offline Tencent m1/m5 extrema comparison with exact coverage gates.

Reads only previously saved original Tencent bytes and re-verifies all eleven
receipts. A 240-row m1 limit must never imply complete coverage of multiple
days. Time-label convention is not independently authenticated.
"""
import argparse
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from collector.tencent_archived_minute_audit import replay
from collector.tencent_eight_sample_pilot import MINUTE_SYMBOLS, PERIODS
from collector.p1_tencent_minute_probe import parse


def labels(day,period):
    # Current provider research hypothesis: minute-ending labels.
    s=day.replace("-","")
    if period=="m1":
        return {s+f"{h:02d}{m:02d}" for h,a,b in
                ((9,31,59),(10,0,59),(11,0,30),(13,1,59),(14,0,59),(15,0,0))
                for m in range(a,b+1)}
    if period=="m5":
        return {s+f"{h:02d}{m:02d}" for h,a,b in
                ((9,35,55),(10,0,55),(11,0,30),(13,5,55),(14,0,55),(15,0,0))
                for m in range(a,b+1)}
    raise ValueError("unsupported period")


def grouped(rows):
    result=defaultdict(list)
    for r in rows:
        result[r["timestamp_cn"][:8]].append(r)
    return result


def summarize(rows,day,period):
    required=labels(f"{day[:4]}-{day[4:6]}-{day[6:]}",period)
    observed={r["timestamp_cn"] for r in rows}
    values=lambda k: [Decimal(str(r[k])) for r in rows]
    return {
        "observed_count":len(rows),
        "expected_count":len(required),
        "missing_count":len(required-observed),
        "unexpected_count":len(observed-required),
        "full_canonical_label_coverage":len(rows)==len(required) and observed==required,
        "earliest_cn":rows[0]["timestamp_cn"] if rows else None,
        "latest_cn":rows[-1]["timestamp_cn"] if rows else None,
        "high":str(max(values("high"))) if rows else None,
        "low":str(min(values("low"))) if rows else None,
    }


def audit(root):
    root=Path(root)
    evidence=replay(root)
    if not evidence["source_sha256_reverified"]:
        raise ValueError("archived hashes not verified")
    observations=[]
    for symbol in MINUTE_SYMBOLS:
        data={}
        for period in ("m1","m5"):
            index=1+MINUTE_SYMBOLS.index(symbol)*len(PERIODS)+PERIODS.index(period)
            folder=root/f"{index:02d}_{symbol}_{period}"
            raw=(folder/"response.bin").read_bytes()
            data[period]=grouped(parse(raw,symbol,period))
        for day in sorted(set(data["m1"])|set(data["m5"])):
            m1=summarize(data["m1"].get(day,[]),day,"m1")
            m5=summarize(data["m5"].get(day,[]),day,"m5")
            full=m1["full_canonical_label_coverage"] and m5["full_canonical_label_coverage"]
            if not data["m1"].get(day) or not data["m5"].get(day):
                status="NO_SAME_DAY_OVERLAP"
            elif full:
                status="FULL_CANONICAL_COVERAGE_RESEARCH_ONLY"
            else:
                status="PARTIAL_COVERAGE_DO_NOT_COMPARE_DAILY_EXTREMES"
            result={
                "symbol":symbol,"day":day,"status":status,
                "m1":m1,"m5":m5,
                "full_day_extrema_comparable":full,
                "daily_extrema_agree_within_1_cent":(
                    abs(Decimal(m1["high"])-Decimal(m5["high"]))<=Decimal("0.01")
                    and abs(Decimal(m1["low"])-Decimal(m5["low"]))<=Decimal("0.01")
                ) if full else None,
            }
            observations.append(result)
    full=[x for x in observations if x["full_day_extrema_comparable"]]
    return {
        "phase":"TENCENT_ORIGINAL_M1_M5_EXACT_DAY_COVERAGE_AUDIT",
        "status":"FULL_DAY_RESEARCH_COMPARISONS_OBSERVED" if full
                 else "NO_FULL_DAY_COMPARABLE_M1_M5_EVIDENCE",
        "observations":observations,
        "full_day_compared":len(full),
        "full_day_disagreements":sum(x["daily_extrema_agree_within_1_cent"] is False for x in full),
        "source_original_sha_verified":True,
        "minute_end_label_convention_officially_verified":False,
        "auction_extrema_verified":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    result=audit(args.archive_root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":main()
