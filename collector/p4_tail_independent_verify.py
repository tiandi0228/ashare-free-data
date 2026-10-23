"""Independently verify captured P4 tail rows against exact missing exit dates."""
import argparse,csv,hashlib,json
from pathlib import Path
from collector.p2_independent_bars import audit_csv
from collector.p4_real_exit_availability import audit
from collector.p4_curated_session_exit import research_exit
from collector.p2_independent_bars import assess

def verify(archive,tail):
    source=audit(archive);tasks={t["code"]:t for t in source["tail_backfill_requests"]}
    folder=Path(tail);manifest=json.loads((folder/"backfill_attempt.json").read_text())
    if manifest.get("trade_gate")!="BLOCKED" or not manifest.get("source_archive_unchanged"):
        raise ValueError("unsafe capture manifest")
    source_targets={}
    for receipt in sorted(Path(archive).glob('*/shard_*/quality.json')):
        verified=assess(receipt.parent)
        for record in verified['details']:
            code=record['code']
            if code not in tasks:continue
            filename=code.replace('.','_')+'.csv'
            rows=list(csv.DictReader((receipt.parent/filename).read_text(encoding='utf-8-sig').splitlines()))
            last_day=rows[-1]['date']
            targets=[]
            for row in rows:
                if row['date']<='2025-12-31' or row['tradestatus']!='1':continue
                try:target=research_exit(row['date'])['candidate_earlier_exit']
                except ValueError:continue
                if target>last_day:targets.append(target)
            source_targets[code]=targets
    seen=set();count=0;matched=0;details=[]
    for item in manifest["results"]:
        code=item["code"]
        if code in seen or code not in tasks:raise ValueError("duplicate or unknown source issuer")
        seen.add(code)
        if item["status"]!="OBSERVED_RESEARCH_ONLY":continue
        filename=code.replace(".","_")+"_tail.csv"
        if item.get("filename")!=filename:raise ValueError("unsafe file path")
        raw=(folder/filename).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item["sha256"]:raise ValueError("tail SHA mismatch")
        stats=audit_csv(raw,code)
        if stats["total_rows"]!=item["rows"] or stats["active_rows"]!=item["active"] or stats["vendor_suspended_rows"]!=item["vendor_suspended"]:
            raise ValueError("tail receipt mismatch")
        task=tasks[code]
        rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
        if any(row["date"]<task["earliest_missing_target"] or row["date"]>task["latest_missing_target"] for row in rows):
            raise ValueError("tail outside requested range")
        distinct={row["date"]:row for row in rows}
        targets=source_targets.get(code,[])
        proven=sum(target in distinct for target in targets)
        active=sum(target in distinct and distinct[target]["tradestatus"]=="1" for target in targets)
        matched+=proven
        count+=len(rows)
        details.append({"code":code,"recovered_dates":sorted(distinct),"rows":len(rows),
                        "missing_exit_observations":len(targets),"restored_exit_date_observations":proven,
                        "restored_vendor_active_observations":active})
    if len(seen)!=manifest["requested_issuers"] or count!=manifest["recovered_target_rows"]:
        raise ValueError("capture count mismatch")
    if matched>source["missing_beyond_source_end"]:raise ValueError("recovery overcount")
    return {"phase":"P4_INDEPENDENT_TAIL_RECOVERY_AUDIT","verified_source_rows":count,
            "restored_exit_date_observations":matched,
            "remaining_exit_date_observations":source["missing_beyond_source_end"]-matched,
            "verified_source_issuers":len(details),"row_date_details":details,
            "specific_exit_observations_proven_recovered":matched>0,
            "source_tail_date_coverage_only":True,"archive_merged":False,
            "historical_PIT_verified":False,"fills_verified":0,
            "trade_gate":"BLOCKED","orders":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--archive",required=True);p.add_argument("--tail",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=verify(a.archive,a.tail);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="row_date_details"}))
if __name__=="__main__":main()
