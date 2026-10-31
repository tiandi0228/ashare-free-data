"""Read-only readiness proof for the exact eight-issuer P4 research cohort.

Independently reopens real archived P1 originals before daily vendor calls.
This is NOT historical PIT/ST certification or buy-signal authorization.
"""
import argparse,csv,hashlib,json,re,subprocess
from pathlib import Path
from collector.baostock_batch import END
from collector.p2_independent_bars import assess
from collector.p4_current_tail_ma20_research import PILOT_SHARD,baseline_items

COHORT=(
    "sh.601100","sh.601101","sh.601106","sh.601107",
    "sh.601108","sh.601111","sh.601112","sh.601113",
)

def inspect(root,commit=None):
    epoch=Path(root)
    status=json.loads((epoch/"archive_status.json").read_text())
    source=status.get("source_sha256")
    if (not isinstance(source,str) or not re.fullmatch("[0-9a-f]{64}",source)
        or epoch.name!=source[:16] or status.get("trade_gate")!="BLOCKED"
        or 98 not in status.get("archived_shards",[])):
        raise ValueError("missing trustworthy immutable P1 pilot shard status")
    selected=baseline_items(epoch,8)  # calls independent P2 source/receipt SHA replay
    codes=tuple(x[0] for x in selected)
    if set(codes)!=set(COHORT) or len(codes)!=8:
        raise ValueError("frozen P4 eight-issuer roster differs from authentic archive")
    verified=assess(epoch/PILOT_SHARD)
    if {d["code"] for d in verified["details"]}!=set(COHORT):
        raise ValueError("P2 independently authenticated issuer cohort mismatch")
    details=[]
    for code,raw,rows in selected:
        actual=next(d for d in verified["details"] if d["code"]==code)
        tradable=sum(row["tradestatus"]=="1" for row in rows)
        if (not rows or rows[-1]["date"]!=END
            or actual["last"]!=END or tradable<20
            or actual["total_rows"]!=len(rows)
            or len(raw)>250000):
            raise ValueError("frozen historical anchor missing or insufficient MA20 closes")
        details.append({"code":code,"frozen_end":END,
            "baseline_csv_sha256":hashlib.sha256(raw).hexdigest(),
            "original_rows":len(rows),"active_bars":tradable})
    if commit is not None and not re.fullmatch("[0-9a-f]{40}",commit):
        raise ValueError("invalid pinned archive git commit")
    return {"phase":"P4_REAL_ARCHIVE_COHORT_PREFLIGHT",
        "status":"EIGHT_SOURCE_ORIGINALS_INDEPENDENTLY_VERIFIED",
        "source_epoch_sha256":source,"source_archive_commit":commit,
        "pilot_shard":PILOT_SHARD,"verified_issuers":len(details),
        "source_details":details,
        "p1_immutable_historical_end":END,
        "ready_for_bounded_vendor_research_attempt":True,
        "historical_PIT_verified":False,"official_ST_halt_verified":False,
        "complete_mainboard_coverage":False,"strategy_buy_signals_authorized":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--archive-commit")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=inspect(a.root,a.archive_commit)
    destination=Path(a.out);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="source_details"}))

if __name__=="__main__":main()
