"""Research-only inferred session grid from real P2 vendor dates.

Intersection/union of vendor dates is NOT an authenticated exchange calendar.
"""
import argparse,csv,json
from collections import Counter
from datetime import date
from pathlib import Path
from collector.p2_independent_bars import assess

def audit(root):
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("no archived source receipts")
    dates=Counter();issuers=0
    for receipt in receipts:
        report=assess(receipt.parent)
        for item in report["details"]:
            issuers+=1
            raw=(receipt.parent/(item["code"].replace(".","_")+".csv")).read_text(encoding="utf-8-sig")
            days={date.fromisoformat(r["date"]) for r in csv.DictReader(raw.splitlines())}
            dates.update(days)
    if not dates:raise ValueError("no vendor session evidence")
    full=sum(v==issuers for v in dates.values())
    partial=len(dates)-full
    return {"phase":"P4_VENDOR_SESSION_COVERAGE_GAP","verified_issuers":issuers,
            "distinct_vendor_dates":len(dates),"all_issuer_dates":full,
            "partially_covered_dates":partial,
            "historical_exchange_calendar_authenticated":False,
            "missing_dates_are_exchange_holidays":False,
            "historical_session_intervals_certified":False,
            "trades_or_returns_computed":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=audit(a.root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
