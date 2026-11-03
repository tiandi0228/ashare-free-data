"""Fail-closed P1 missed-slot recovery eligibility. Research-only; NO TRADES.

Safeguards are evaluated using the live P1 workflow API, never the generic run
list. A proposed recovery is not executed in this version: dispatch is disabled.
The observation report is suitable for auditing before any future activation.
"""
import argparse,datetime as dt,json,os,re,subprocess
from pathlib import Path
from zoneinfo import ZoneInfo
from collector.p1_schedule_watchdog import audit,iso,slots,TARGET,TZ

def eligibility(now,runs,*,total_count=None):
    if now.tzinfo is None or not isinstance(runs,list) or not runs:
        return refusal(now,"RUN_COVERAGE_UNVERIFIED")
    if type(total_count) is not int or total_count<0 or total_count<len(runs):
        return refusal(now,"RUN_LIST_TRUNCATED_OR_INVALID")
    # The target workflow may have >100 historical runs, so listing is capped by
    # the lookback, not by historical total; require at least 24h of recent records.
    # An empty 24h history is not an assurance of no concurrency.
    parsed=[]
    for run in runs:
        if not isinstance(run,dict):
            return refusal(now,"MALFORMED_RUN_RECORD")
        if run.get("path")!=".github/workflows/"+TARGET:
            return refusal(now,"WRONG_WORKFLOW_RUNS")
        if run.get("event") not in ("schedule","workflow_dispatch","push"):
            return refusal(now,"UNKNOWN_RUN_EVENT")
        try:stamp=iso(run["created_at"]).astimezone(TZ)
        except (KeyError,ValueError,TypeError,AttributeError):
            return refusal(now,"MALFORMED_RUN_TIMESTAMP")
        parsed.append((stamp,run))
    most_recent=max(t for t,_ in parsed)
    if now.astimezone(TZ)-most_recent>dt.timedelta(hours=24):
        return refusal(now,"RUN_HISTORY_TOO_OLD")
    # If the first page is saturated, a second unseen page may contain runs
    # around the target slot; require the oldest returned run predates it.
    candidate_slots=slots(now)
    if not candidate_slots:
        return refusal(now,"NO_ELIGIBLE_SLOT")
    if min(t for t,_ in parsed)>candidate_slots[0]-dt.timedelta(minutes=2):
        return refusal(now,"RUN_HISTORY_DOES_NOT_COVER_SLOT",slot=candidate_slots[0])
    watchdog=audit(now,runs)
    slot=iso(watchdog["scheduled_slot_beijing"]).astimezone(TZ)
    if watchdog["state"]!="SUSPECTED_MISSED_SCHEDULE":
        return refusal(now,"SCHEDULE_SLOT_NOT_MISSING",slot=slot)
    elapsed=now.astimezone(TZ)-slot
    # Require an additional 20-minute grace beyond the existing watchdog 45m,
    # and NEVER recover an old slot (>90min) that could create stale ingestion.
    if not dt.timedelta(minutes=65)<=elapsed<=dt.timedelta(minutes=90):
        return refusal(now,"OUTSIDE_SAFE_RECOVERY_WINDOW",slot=slot)
    for stamp,run in parsed:
        if run.get("status") in ("queued","in_progress","requested","waiting","pending"):
            return refusal(now,"P1_RUN_ACTIVE",slot=slot)
        if run.get("status")!="completed":
            return refusal(now,"UNKNOWN_RUN_STATUS",slot=slot)
        # A manually started, pushed or scheduled run after the missed slot
        # already supplies a historical-data collection opportunity.
        if stamp>=slot-dt.timedelta(minutes=2):
            return refusal(now,"P1_RUN_ALREADY_STARTED_AFTER_SLOT",slot=slot)
    return {
        "state":"ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW",
        "slot":slot.isoformat(),
        "reason":"SCHEDULE_SLOT_MISSING_WITH_NO_RECENT_OR_ACTIVE_RUN",
        "requested_shards":1,
        "auto_dispatch_enabled":False,
        "auto_dispatched":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def refusal(now,reason,slot=None):
    return {
        "state":"RECOVERY_BLOCKED",
        "slot":slot.isoformat() if slot else None,
        "reason":reason,
        "requested_shards":0,
        "auto_dispatch_enabled":False,
        "auto_dispatched":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def workflow_runs(repo):
    if not isinstance(repo,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
        raise ValueError("invalid repository")
    out=subprocess.run(["gh","api",f"repos/{repo}/actions/workflows/{TARGET}/runs",
                        "--method","GET","-f","per_page=100"],
                       capture_output=True,text=True,timeout=35,check=True)
    data=json.loads(out.stdout)
    if not isinstance(data,dict) or not isinstance(data.get("workflow_runs"),list):
        raise ValueError("GitHub workflow runs API response invalid")
    return data["workflow_runs"],data.get("total_count")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    args=p.parse_args()
    now=dt.datetime.now(TZ)
    try:
        runs,total=workflow_runs(args.repo)
        report=eligibility(now,runs,total_count=total)
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        report=refusal(now,"LIVE_RUN_API_UNAVAILABLE")
    report["phase"]="P1_MISSED_SLOT_RECOVERY_READ_ONLY_GUARD"
    report["checked_at_beijing"]=now.isoformat()
    report["operating_mode"]="DRY_RUN_NO_DISPATCH"
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    if report["state"]=="ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW":
        print("::warning::P1 recovery candidate found, but NO automatic dispatch is enabled.")
if __name__=="__main__":main()
