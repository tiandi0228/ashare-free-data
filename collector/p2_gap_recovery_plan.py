"""Separate historical indicator gaps from prospective recovery; never bridge suspension."""
import argparse,csv,hashlib,json
from pathlib import Path
from datetime import date,timedelta
from collector.p2_original_gap_window_triage import diagnose
from collector.p2_independent_bars import audit_csv

def recovery(rows,asof):
    cutoff=date.fromisoformat(asof)
    streak=0
    for row in reversed(rows):
        if date.fromisoformat(row["date"])>cutoff:continue
        if row["tradestatus"]!="1":break
        streak+=1
    remaining=max(0,21-streak)
    return {"trailing_tradable_observations":streak,"additional_consecutive_observations_needed":remaining,
            "historical_gap_resolved":False,"future_recovery_not_guaranteed":True}

def run(coverage,root):
    report=diagnose(coverage,root)
    rows=[]
    for r in report["results"]:
        raw=(root/r["source_shard"]/(r["issuer"].replace(".","_")+".csv")).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r["original_csv_sha256"]:raise ValueError("original SHA mismatch")
        audit_csv(raw,r["issuer"])
        plan=recovery(list(csv.DictReader(raw.decode("utf-8-sig").splitlines())),r["asof_date"])
        if plan["additional_consecutive_observations_needed"]==0:raise ValueError("gap contradicts recovery plan")
        rows.append(dict(**r,**plan))
    return dict(source_epoch_sha256=report["source_epoch_sha256"],asof=report["asof_completed_day"],
                gap_issuers=len(rows),rows=rows,coverage_gaps_resolved=0,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--coverage",type=Path,required=True);p.add_argument("--archive-epoch",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.coverage.read_bytes()),a.archive_epoch)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P2_RECOVERY_PLAN:",json.dumps({k:v for k,v in r.items() if k!="rows"}))
