"""Research-only real vendor-bar exit-date availability, never fill inference."""
import argparse,csv,json
from collections import Counter
from pathlib import Path
from collector.p2_independent_bars import assess
from collector.p4_curated_session_exit import research_exit

def audit(root,cutoff="2025-12-31"):
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("missing independently validated archive")
    counts=Counter();examples=[];backfill={};vendor_halts=[]
    for receipt in receipts:
        validated=assess(receipt.parent)
        for item in validated["details"]:
            counts["verified_issuers"]+=1
            p=receipt.parent/(item["code"].replace(".","_")+".csv")
            rows=list(csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines()))
            dates={x["date"]:x for x in rows}
            last_vendor_date=rows[-1]["date"]
            for row in rows:
                day=row["date"]
                if day<=cutoff or row["tradestatus"]!="1":continue
                counts["active_holdout_entry_dates"]+=1
                try:exit_plan=research_exit(day)
                except ValueError:
                    counts["calendar_unavailable"]+=1;continue
                target=exit_plan["candidate_earlier_exit"]
                next_row=dates.get(target)
                if next_row is None:
                    counts["target_vendor_row_missing"]+=1
                    kind="BEYOND_SOURCE_END" if target>last_vendor_date else "INTERNAL_MISSING_DATE"
                    counts["missing_"+kind.lower()]+=1
                    if kind=="BEYOND_SOURCE_END":
                        code=item["code"]
                        task=backfill.setdefault(code,{"code":code,"last_archived_date":last_vendor_date,"earliest_missing_target":target,"latest_missing_target":target,"affected_entry_observations":0})
                        task["earliest_missing_target"]=min(task["earliest_missing_target"],target)
                        task["latest_missing_target"]=max(task["latest_missing_target"],target)
                        task["affected_entry_observations"]+=1
                    if len(examples)<20:examples.append({"code":item["code"],"entry":day,"target":target,"reason":kind})
                elif next_row["tradestatus"]=="0":
                    counts["target_vendor_suspended"]+=1
                    vendor_halts.append({"code":item["code"],"entry_date":day,"target_exit_date":target,"vendor_status":"0","official_halt_verified":False})
                    if len(examples)<20:examples.append({"code":item["code"],"entry":day,"target":target,"reason":"VENDOR_SUSPENDED"})
                elif next_row["tradestatus"]=="1":
                    counts["target_vendor_active"]+=1
                else:raise ValueError("unrecognized vendor trade status")
    keys=("verified_issuers","active_holdout_entry_dates","calendar_unavailable","target_vendor_row_missing","target_vendor_suspended","target_vendor_active","missing_beyond_source_end","missing_internal_missing_date")
    for key in keys:counts[key]+=0
    assert counts["active_holdout_entry_dates"]==sum(counts[k] for k in ("calendar_unavailable","target_vendor_row_missing","target_vendor_suspended","target_vendor_active"))
    assert counts["target_vendor_row_missing"]==counts["missing_beyond_source_end"]+counts["missing_internal_missing_date"]
    if sum(x["affected_entry_observations"] for x in backfill.values())!=counts["missing_beyond_source_end"] or len(vendor_halts)!=counts["target_vendor_suspended"]:
        raise ValueError("unreconciled tail requests or halt observations")
    return {"phase":"P4_REAL_HOLDOUT_EXIT_DATE_ROW_AVAILABILITY",**counts,
            "tail_backfill_issuer_count":len(backfill),
            "tail_backfill_requests":sorted(backfill.values(),key=lambda x:x["code"]),
            "vendor_halt_crosscheck_queue":vendor_halts,
            "tail_requests_are_not_recovered_bars":True,
            "exceptions_sample":examples,
            "entry_dates_are_not_filled_orders":True,
            "vendor_active_does_not_prove_fill":True,
            "exchange_calendar_authenticated":False,"halt_status_independently_authenticated":False,
            "orders_simulated":0,"fills_verified":0,"returns_computed":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=audit(a.root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="exceptions_sample"},ensure_ascii=False))
if __name__=="__main__":main()
