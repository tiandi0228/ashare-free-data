"""Read-only cross-workflow P1 schedule health audit.

GitHub Actions cron is best effort. A missing run is a suspected missed slot,
NOT proof that a source collection failed or that GitHub disabled the workflow.
No dispatch, data writes, order placement or trading authorization.
"""
import argparse,datetime as dt,json,os,subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Shanghai")
TARGET="p1-fresh-vendor-roster.yml"
# Beijing weekday slots in the existing approved workflow; no change to the
# historical collection cadence or number of requested shards.
WEEKDAY_HOURS=(1,8,9,11,13,15,17,19,21,23)
WEEKEND_HOURS=(9,15,19,23)

def slots(now,grace_minutes=45):
    if now.tzinfo is None:raise ValueError("timezone-aware current time required")
    local=now.astimezone(TZ)
    cutoff=local-dt.timedelta(minutes=grace_minutes)
    eligible=[]
    for offset in range(3):
        day=local.date()-dt.timedelta(days=offset)
        hours=WEEKDAY_HOURS if day.weekday()<5 else WEEKEND_HOURS
        for hour in hours:
            when=dt.datetime.combine(day,dt.time(hour,10),TZ)
            if when<=cutoff:eligible.append(when)
    return sorted(eligible,reverse=True)

def scheduled_cron(slot):
    """Expected *source* cron for a Beijing-local scheduled time, not run creation."""
    if slot.tzinfo is None:
        raise ValueError("scheduled slot needs timezone")
    when=slot.astimezone(TZ)
    utc_hour=when.astimezone(dt.timezone.utc).hour
    if when.weekday()<5:
        day_pattern="0-4" if when.hour==1 else "1-5"
    else:
        day_pattern="6,0"
    return f"10 {utc_hour} * * {day_pattern}"

def iso(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))

def audit(now,runs):
    if not isinstance(runs,list):raise ValueError("GitHub Actions run list unavailable")
    candidates=slots(now)
    if not candidates:raise ValueError("no eligible P1 schedule slot")
    slot=candidates[0]
    # Creation may be delayed by hours. Timestamp proximity alone cannot
    # identify the nominal scheduled cron; refuse ambiguous attribution.
    expected_title=f"P1 origin {scheduled_cron(slot)} [NO TRADES]"
    observed=[]
    unknown=[]
    for run in runs:
        if not isinstance(run,dict):continue
        if run.get("event")!="schedule":continue
        if run.get("path")!=".github/workflows/p1-fresh-vendor-roster.yml":
            continue
        created=run.get("created_at")
        if not isinstance(created,str):continue
        try:stamp=iso(created).astimezone(TZ)
        except ValueError:continue
        # Do not attribute a different slot to this one.
        if slot-dt.timedelta(minutes=2)<=stamp<=slot+dt.timedelta(minutes=45):
            if run.get("display_title")==expected_title:
                observed.append((stamp,run))
            else:
                # Legacy runs with no cron title, and delayed runs belonging
                # to a different cron, are NOT proof of this source slot.
                unknown.append((stamp,run))
    latest=max(observed,key=lambda x:x[0])[1] if observed else None
    if latest is None:
        state=("SCHEDULE_ORIGIN_UNVERIFIED" if unknown
               else "SUSPECTED_MISSED_SCHEDULE")
    elif latest.get("status")!="completed":state="SCHEDULE_RUN_IN_PROGRESS"
    elif latest.get("conclusion")=="success":state="SCHEDULE_RUN_COMPLETED"
    else:state="SCHEDULE_RUN_FAILED_OR_CANCELLED"
    return {
        "phase":"P1_READ_ONLY_SCHEDULE_WATCHDOG",
        "checked_at_beijing":now.astimezone(TZ).isoformat(),
        "scheduled_slot_beijing":slot.isoformat(),
        "grace_minutes":45,
        "state":state,
        "matched_schedule_run_id":latest.get("id") if latest else None,
        "matched_schedule_conclusion":latest.get("conclusion") if latest else None,
        "expected_scheduled_cron":scheduled_cron(slot),
        "unattributed_schedule_run_count":len(unknown),
        "run_count_from_api":len(runs),
        "scope":"BEST_EFFORT_GITHUB_SCHEDULE_ONLY",
        "uncertainty":"RUN_LIST_CAN_BE_INCOMPLETE_OR_GITHUB_CRON_DELAYED",
        "no_automatic_dispatch":True,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
    }

def api_runs(repo):
    if not isinstance(repo,str) or repo.count("/")!=1:raise ValueError("invalid repo")
    args=["gh","api",f"repos/{repo}/actions/workflows/{TARGET}/runs",
          "-f","per_page=100","--method","GET"]
    out=subprocess.run(args,capture_output=True,text=True,timeout=30,check=True)
    data=json.loads(out.stdout)
    if not isinstance(data,dict) or not isinstance(data.get("workflow_runs"),list):
        raise ValueError("invalid GitHub workflow runs response")
    return data["workflow_runs"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    a=p.parse_args()
    now=dt.datetime.now(TZ)
    result=audit(now,api_runs(a.repo))
    dst=Path(a.out);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"state":result["state"],
                      "slot":result["scheduled_slot_beijing"],
                      "run_id":result["matched_schedule_run_id"],
                      "trade_gate":"BLOCKED"},ensure_ascii=False))
    if result["state"]=="SUSPECTED_MISSED_SCHEDULE":
        print("::warning::P1 historical schedule slot has no matching Actions scheduled run (best-effort audit).")
    elif result["state"]=="SCHEDULE_ORIGIN_UNVERIFIED":
        print("::warning::P1 schedule runs near slot have missing/mismatched cron provenance; not proof of slot execution.")
    elif result["state"]=="SCHEDULE_RUN_FAILED_OR_CANCELLED":
        print("::warning::P1 historical schedule run failed/cancelled; inspect that run.")

if __name__=="__main__":main()
