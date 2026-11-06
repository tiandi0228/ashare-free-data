"""Pick the freshest completed main-branch P2/P3/P4 observation artifacts.

Independent per-lane timestamps mean this is a latest-successful snapshots
dashboard, not one synchronized market event, and not historical PIT proof.
"""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKFLOWS={
    "p2":"p2-real-archive-feature-observation.yml",
    "p3":"p3-full-p1-official-scout.yml",
    "p4":"p4-real-ma20-forward-observation.yml",
}
def select(rows):
    if not isinstance(rows,list):raise ValueError("missing GitHub completed runs")
    candidates=[]
    for row in rows:
        if not isinstance(row,dict):continue
        if row.get("conclusion")!="success" or row.get("status")!="completed" or row.get("headBranch")!="main":
            continue
        rid=row.get("databaseId");created=row.get("createdAt")
        if type(rid) is not int or rid<=0 or not isinstance(created,str):continue
        try:dt=datetime.fromisoformat(created.replace("Z","+00:00"))
        except ValueError:continue
        if dt.tzinfo is None:continue
        candidates.append((dt.astimezone(timezone.utc),rid))
    if not candidates:raise ValueError("no verified successful main-branch run")
    dt,rid=max(candidates)
    return {"run_id":rid,"created_at_utc":dt.isoformat(),
            "source_run_success_and_main_verified":True}

def latest(fetch=None):
    if fetch is None:
        def fetch(workflow):
            value=subprocess.check_output(
                ["gh","run","list","--workflow",workflow,"--limit","30",
                 "--json","databaseId,conclusion,status,headBranch,createdAt"],
                text=True,timeout=35)
            return json.loads(value)
    data={lane:select(fetch(workflow)) for lane,workflow in WORKFLOWS.items()}
    if len({v["run_id"] for v in data.values()})!=3:
        raise ValueError("run identities overlap across distinct workflows")
    return {"phase":"P234_NEWEST_SUCCESSFUL_SOURCE_RUN_PROVENANCE",
            "selection":data,"cohort_synchronized":False,
            "source_artifacts_not_official_pit":True,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    report=latest()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__": main()
