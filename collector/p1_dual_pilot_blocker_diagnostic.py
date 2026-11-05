"""Explain P1 dual-pilot scale blockers from GitHub Actions evidence. Never scales."""
import argparse
import json
import subprocess
from pathlib import Path

TARGET = ".github/workflows/p1-fresh-vendor-roster.yml"
MAX = 100

def diagnose(review, history):
    if (not isinstance(review, dict)
        or review.get("phase") != "P1_DUAL_PILOT_READ_ONLY_SCALE_REVIEW"
        or review.get("trade_gate") != "BLOCKED"
        or review.get("historical_PIT_verified") is not False
        or review.get("automatic_shard_increase_authorized") is not False
        or review.get("orders") != [] or review.get("executable_candidates") != []):
        raise ValueError("untrusted pilot review")
    if (not isinstance(history, dict)
        or type(history.get("total_count")) is not int
        or history["total_count"] < 0
        or not isinstance(history.get("workflow_runs"),list)
        or not 1 <= len(history["workflow_runs"]) <= MAX
        or history["total_count"] < len(history["workflow_runs"])):
        raise ValueError("invalid workflow-scoped schedule history")
    rows=history["workflow_runs"]
    ids=set()
    for x in rows:
        if (not isinstance(x,dict) or type(x.get("id")) is not int or x["id"]<=0
            or x["id"] in ids
            or x.get("event")!="schedule"
            or x.get("head_branch")!="main"
            or not isinstance(x.get("path"),str)
            or not (x["path"]==TARGET or x["path"].startswith(TARGET+"@"))
            or x.get("status") not in ("completed","queued","in_progress","requested","waiting","pending")
            or x.get("conclusion") not in (None,"success","failure","cancelled","timed_out","skipped","action_required","neutral")):
            raise ValueError("malformed or unrelated P1 scheduled run")
        ids.add(x["id"])
    claimed=review.get("schedule_problem_run_ids",[])
    if (not isinstance(claimed,list) or any(type(x) is not int or x<=0 for x in claimed)
        or len(set(claimed))!=len(claimed)):
        raise ValueError("untrusted problem IDs")
    selected=review.get("reviewed_scheduled_run_ids",[])
    if not isinstance(selected,list) or any(type(x) is not int or x<=0 for x in selected):
        raise ValueError("invalid selected pilot run IDs")
    # The report's comparison scope is the only legitimate denominator.
    # Never silently treat page 1 as complete for an older pilot period.
    checked=review.get("schedule_checked_run_ids",[])
    if not isinstance(checked,list) or any(type(x) is not int or x<=0 for x in checked):
        raise ValueError("invalid checked run IDs")
    known={x["id"]:x for x in rows}
    if any(i not in known for i in checked) or len(set(checked))!=len(checked):
        return {"phase":"P1_DUAL_PILOT_BLOCKER_DIAGNOSIS",
            "status":"HISTORY_INCOMPLETE_NO_DECISION",
            "missing_checked_runs":sorted(set(checked)-ids),
            "trade_gate":"BLOCKED","orders":[],
            "automatic_shard_increase_authorized":False}
    if not set(claimed).issubset(checked):
        raise ValueError("pilot report problem outside checked history")
    computed={i for i in checked if (known[i]["status"]!="completed"
                                     or known[i]["conclusion"]!="success")}
    if computed != set(claimed):
        raise ValueError("pilot scale review and GitHub status disagree")
    blockers=[{"run_id":i,"status":known[i]["status"],
               "conclusion":known[i]["conclusion"],
               "created_at_utc":known[i].get("created_at"),
               "note":"WORKFLOW_RUN_STATUS_NOT_A_SHARD_FAILURE_CAUSE"}
              for i in sorted(computed,reverse=True)]
    counts={}
    for row in blockers:
        label=row["conclusion"] if row["status"]=="completed" else "not_completed"
        counts[label]=counts.get(label,0)+1
    return {"phase":"P1_DUAL_PILOT_BLOCKER_DIAGNOSIS",
        "status":("INTERVENING_SCHEDULE_RUN_ISSUES" if blockers
                  else "NO_SCHEDULE_PROBLEMS_IN_BOUNDED_REVIEW"),
        "review_status":review.get("status"),
        "reviewed_pilot_run_ids":selected,
        "checked_schedule_runs":len(checked),
        "problem_count":len(blockers),
        "problem_status_counts":dict(sorted(counts.items())),
        "problem_runs":blockers,
        "root_cause_verified":False,
        "next_action":"INSPECT_INDIVIDUAL_JOB_LOGS_NOT_AUTOMATICALLY_SCALE",
        "automatic_shard_increase_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--review",required=True)
    p.add_argument("--repo",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if a.repo.count("/")!=1 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-" for c in a.repo):
        raise ValueError("invalid repository")
    history=json.loads(subprocess.check_output([
        "gh","api",f"repos/{a.repo}/actions/workflows/p1-fresh-vendor-roster.yml/runs",
        "--method","GET","-f","event=schedule","-f","per_page=100"],timeout=30))
    result=diagnose(json.loads(Path(a.review).read_text()),history)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="problem_runs"}))
if __name__=="__main__":main()
