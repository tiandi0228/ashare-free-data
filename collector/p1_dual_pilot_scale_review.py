"""Read-only P1 dual-pilot scaling review from permanent same-epoch GitHub receipts.

A receipt represents only one audited run. Missing or expired failed runs are
not observable here: three recorded successes permit human review, NEVER
automated scaling, PIT certification or trading.
"""
import argparse
import base64
import json
import os
import re
import subprocess
from pathlib import Path

from collector.p1_checkpoint import epoch_path, gh

PILOT_CRON = "10 15 * * 1-5"
FILE_NAME = re.compile(r"run_([1-9][0-9]*)_attempt_([1-9][0-9]*)\.json\Z")
MIN_RECORDED_SUCCESSES = 3
MAX_READS = 12


def inspect(receipts, epoch):
    epoch_path(epoch)
    if not isinstance(receipts, list):
        raise ValueError("pilot receipt collection must be a list")
    by_run = {}
    for row in receipts:
        if not isinstance(row, dict):
            raise ValueError("invalid pilot receipt")
        run_id,attempt = row.get("run_id"),row.get("run_attempt")
        if (row.get("phase") != "P1_DURABLE_DUAL_SHARD_PILOT_RECEIPT"
                or row.get("source_sha256") != epoch
                or row.get("requested_shards") != 2
                or row.get("archive_csv_replay_enabled") is not True
                or row.get("archive_gap_issuers") != 0
                or row.get("trade_gate") != "BLOCKED"
                or row.get("historical_PIT_verified") is not False
                or row.get("orders") != [] or row.get("executable_candidates") != []
                or type(run_id) is not int or run_id <= 0
                or type(attempt) is not int or attempt <= 0):
            raise ValueError("untrusted pilot receipt")
        is_sched = row.get("trigger") == "schedule"
        if not is_sched and row.get("trigger") != "workflow_dispatch":
            raise ValueError("unrecognized pilot trigger")
        if (is_sched and row.get("trigger_cron_utc") != PILOT_CRON
                or not is_sched and row.get("trigger_cron_utc") is not None):
            raise ValueError("untrusted pilot schedule")
        selected,actual = row.get("selected_shards"),row.get("new_selected_shards")
        n = row.get("new_shards_durably_accepted")
        before,after = row.get("checkpoint_shards_before"),row.get("checkpoint_shards_after")
        if (not isinstance(selected,list) or not 1<=len(selected)<=2
                or any(type(i) is not int or i<0 for i in selected)
                or len(set(selected))!=len(selected)
                or not isinstance(actual,list)
                or any(type(i) is not int for i in actual)
                or len(set(actual))!=len(actual)
                or not set(actual).issubset(selected)
                or type(n) is not int or n!=len(actual)
                or type(before) is not int or before<0
                or type(after) is not int or after!=before+n):
            raise ValueError("pilot receipt checkpoint delta not verified")
        outcome=row.get("dual_pilot_result")
        if outcome not in ("TWO_VERIFIED_SHARDS_ARCHIVED",
                           "FIRST_ARCHIVED_SECOND_REJECTED",
                           "DUAL_PILOT_NOT_YET_PROVEN",
                           "ONLY_ONE_SHARD_PENDING"):
            raise ValueError("unknown pilot result")
        if outcome=="TWO_VERIFIED_SHARDS_ARCHIVED" and (
                len(selected)!=2 or n!=2 or set(actual)!=set(selected)
                or row.get("second_policy_status")!="SECOND_SHARD_VERIFIED"):
            raise ValueError("forged two-shard pilot success")
        if outcome=="FIRST_ARCHIVED_SECOND_REJECTED" and (
                len(selected)!=2 or n!=1 or actual!=[selected[0]]
                or row.get("second_policy_status") not in (
                    "SECOND_FAILED_PRESERVE_FIRST","SECOND_INVALID_PRESERVE_FIRST")):
            raise ValueError("invalid safe fallback")
        if outcome=="ONLY_ONE_SHARD_PENDING" and len(selected)!=1:
            raise ValueError("invalid final-shard receipt")
        existing=by_run.get(run_id)
        if existing is not None and (
                existing["trigger"]!=row["trigger"]
                or existing["source_sha256"]!=epoch):
            raise ValueError("same run has conflicting source or trigger")
        if existing is None or existing["run_attempt"]<attempt:
            by_run[run_id]=row
        elif existing["run_attempt"]==attempt and existing!=row:
            raise ValueError("same run attempt has conflicting receipts")
    ordered=sorted(by_run.values(),key=lambda row:row["run_id"],reverse=True)
    scheduled=[r for r in ordered if r["trigger"]=="schedule"]
    recent=scheduled[:MIN_RECORDED_SUCCESSES]
    success=(len(recent)==MIN_RECORDED_SUCCESSES
             and all(r["dual_pilot_result"]=="TWO_VERIFIED_SHARDS_ARCHIVED"
                     for r in recent))
    decision=("RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION" if success else
              "INSUFFICIENT_SCHEDULED_PILOT_RECEIPTS"
              if len(recent)<MIN_RECORDED_SUCCESSES else
              "RECENT_RECORDED_PILOT_NOT_ALL_SUCCESSFUL")
    return {
        "phase":"P1_DUAL_PILOT_READ_ONLY_SCALE_REVIEW",
        "source_sha256":epoch,
        "recorded_total_unique_runs":len(ordered),
        "recorded_scheduled_runs":len(scheduled),
        "recorded_manual_runs":len(ordered)-len(scheduled),
        "required_recent_recorded_successes":MIN_RECORDED_SUCCESSES,
        "reviewed_scheduled_run_ids":[r["run_id"] for r in recent],
        "reviewed_scheduled_results":[r["dual_pilot_result"] for r in recent],
        "status":decision,
        "unrecorded_or_failed_runs_not_excluded":True,
        "automatic_shard_increase_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
    }


def load_recent_remote(repo,epoch):
    epoch_path(epoch)
    if not isinstance(repo,str) or repo.count("/")!=1:
        raise ValueError("invalid GitHub repository")
    directory=f"evidence/pilot_runs/{epoch[:16]}"
    try:
        listing=json.loads(gh(f"repos/{repo}/contents/{directory}",
                              "-f","ref=main","--method","GET"))
    except subprocess.CalledProcessError as exc:
        if "404" in (exc.stderr or "") and "Not Found" in (exc.stderr or ""):
            return []
        raise
    # GitHub Contents permits up to 1,000 entries per directory. Reviewing
    # only the latest 12 blobs keeps reads bounded while allowing hundreds of
    # immutable pilot runs to accumulate before requiring a paged tree API.
    if not isinstance(listing,list) or len(listing)>=1000:
        raise ValueError("pilot directory exceeds GitHub Contents bounded listing")
    entries=[]
    for item in listing:
        if not isinstance(item,dict):
            raise ValueError("malformed pilot directory entry")
        match=FILE_NAME.fullmatch(str(item.get("name","")))
        if match:
            if item.get("type")!="file" or item.get("path")!=directory+"/"+item["name"]:
                raise ValueError("invalid permanent pilot evidence path")
            entries.append((int(match.group(1)),int(match.group(2)),item["path"]))
    entries.sort(reverse=True)
    result=[]
    for run_id,attempt,path in entries[:MAX_READS]:
        obj=json.loads(gh(f"repos/{repo}/contents/{path}","-f",
                          "ref=main","--method","GET"))
        if (not isinstance(obj,dict) or not obj.get("sha")
                or obj.get("path")!=path
                or obj.get("type")!="file"):
            raise ValueError("missing or mismatched permanent pilot blob")
        data=json.loads(base64.b64decode(obj["content"]).decode())
        # Filename and blob must describe the same immutable Actions run.
        # Otherwise one run could be wrongly credited with another run's
        # verified shards.  This also catches swapped/misrouted blobs.
        if (not isinstance(data,dict)
                or type(data.get("run_id")) is not int
                or data["run_id"]!=run_id
                or type(data.get("run_attempt")) is not int
                or data["run_attempt"]!=attempt
                or data.get("source_sha256")!=epoch):
            raise ValueError("pilot receipt path and source identity mismatch")
        result.append(data)
    return result


def verify_actions_conclusions(report, receipts, repo, *, current_run_id=None):
    """Cross-check receipt claims against completed GitHub Actions runs.

    Only completed successful scheduled runs in the exact workflow qualify.
    The active run cannot certify its own success before it has finished.
    Failed runs that never saved a receipt remain unknown and still require
    separate human inspection of the workflow's full run history.
    """
    if report.get("status") != "RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION":
        return report
    if not isinstance(repo, str) or repo.count("/") != 1:
        raise ValueError("GitHub repository required")
    ids = report["reviewed_scheduled_run_ids"]
    if len(ids) != MIN_RECORDED_SUCCESSES or len(set(ids)) != len(ids):
        raise ValueError("invalid reviewed pilot run IDs")
    match = {}
    for row in receipts:
        if isinstance(row, dict) and type(row.get("run_id")) is int:
            previous = match.get(row["run_id"])
            if previous is None or row["run_attempt"] > previous["run_attempt"]:
                match[row["run_id"]] = row
    outcomes = []
    for run_id in ids:
        receipt = match.get(run_id)
        if receipt is None:
            raise ValueError("pilot run receipt missing from evidence")
        if current_run_id is not None and run_id == current_run_id:
            outcomes.append({"run_id": run_id, "status": "CURRENT_RUN_NOT_COMPLETED"})
            continue
        remote = json.loads(gh(f"repos/{repo}/actions/runs/{run_id}"))
        if (not isinstance(remote, dict)
                or type(remote.get("id")) is not int
                or remote["id"] != run_id):
            raise ValueError("GitHub Actions returned mismatched run ID")
        same_workflow = (
            remote.get("path") == ".github/workflows/p1-fresh-vendor-roster.yml"
            or str(remote.get("path", "")).startswith(
                ".github/workflows/p1-fresh-vendor-roster.yml@")
        )
        good = (same_workflow
                and remote.get("event") == "schedule"
                and remote.get("head_branch") == "main"
                and remote.get("status") == "completed"
                and remote.get("conclusion") == "success"
                and type(remote.get("run_attempt")) is int
                and remote["run_attempt"] == receipt["run_attempt"])
        outcomes.append({
            "run_id": run_id,
            "status": ("CONFIRMED_SUCCESS" if good
                       else "NOT_CONFIRMED_SUCCESS"),
            "conclusion": remote.get("conclusion"),
            "run_attempt_matches": (
                type(remote.get("run_attempt")) is int
                and remote["run_attempt"] == receipt["run_attempt"]),
        })
    proven = all(x["status"] == "CONFIRMED_SUCCESS" for x in outcomes)
    return dict(
        report,
        status=("RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK" if proven else
                "RECORDED_PILOTS_ACTIONS_VERIFICATION_INCOMPLETE"),
        actions_runs_verified=proven,
        reviewed_actions_conclusions=outcomes,
        automatic_shard_increase_authorized=False,
    )


def verify_recent_schedule_health(report, repo, *, current_run_id=None):
    """Conservative check of scheduled runs since the oldest pilot reviewed.

    Even successful dual-pilot receipts do not exclude scheduled failures
    without receipts. GitHub's workflow-scoped history is bounded to 100 runs.
    Treat missing history, failed unrelated scheduled slots and incomplete jobs
    as insufficient evidence for scaling; never authorize changes.
    """
    if report.get("status") != "RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK":
        return report
    if not isinstance(repo, str) or repo.count("/") != 1:
        raise ValueError("GitHub repository required")
    target = report.get("reviewed_scheduled_run_ids")
    if (not isinstance(target, list) or len(target) != MIN_RECORDED_SUCCESSES
            or any(type(n) is not int or n <= 0 for n in target)
            or len(set(target)) != len(target)):
        raise ValueError("invalid reviewed scheduled pilot IDs")
    history = json.loads(gh(
        f"repos/{repo}/actions/workflows/p1-fresh-vendor-roster.yml/runs",
        "-f", "event=schedule", "-f", "per_page=100", "--method", "GET"))
    if (not isinstance(history, dict)
            or type(history.get("total_count")) is not int
            or not isinstance(history.get("workflow_runs"), list)
            or len(history["workflow_runs"]) > 100
            or history["total_count"] < len(history["workflow_runs"])):
        raise ValueError("malformed scheduled workflow history")
    observed = {}
    for run in history["workflow_runs"]:
        if (not isinstance(run, dict)
                or type(run.get("id")) is not int or run["id"] <= 0
                or run["id"] in observed):
            raise ValueError("invalid scheduled run in workflow history")
        observed[run["id"]] = run
    oldest = min(target)
    if not set(target).issubset(observed):
        return dict(report,
                    status="RECORDED_PILOTS_SCHEDULE_HISTORY_INCOMPLETE",
                    schedule_history_complete=False,
                    schedule_checked_run_ids=[],
                    schedule_problem_run_ids=[],
                    automatic_shard_increase_authorized=False)
    watched = [
        run for run in observed.values()
        if run["id"] >= oldest and run["id"] != current_run_id
    ]
    watched.sort(key=lambda r:r["id"], reverse=True)
    problems = []
    for run in watched:
        path = str(run.get("path", ""))
        valid_path = (path == ".github/workflows/p1-fresh-vendor-roster.yml"
                      or path.startswith(
                          ".github/workflows/p1-fresh-vendor-roster.yml@"))
        if (not valid_path or run.get("event") != "schedule"
                or run.get("head_branch") != "main"
                or run.get("status") != "completed"
                or run.get("conclusion") != "success"):
            problems.append(run["id"])
    return dict(
        report,
        status=("RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW" if not problems
                else "RECORDED_PILOTS_INTERVENING_SCHEDULE_FAILURE"),
        schedule_history_complete=True,
        schedule_checked_run_ids=[r["id"] for r in watched],
        schedule_problem_run_ids=problems,
        automatic_shard_increase_authorized=False,
    )


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--repo",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    receipts=load_recent_remote(args.repo,args.source_sha)
    # Exclude the currently running workflow: a job cannot independently
    # certify its own eventual conclusion before the job finishes.
    active=os.environ.get("GITHUB_RUN_ID")
    current=int(active) if active else None
    stable=[r for r in receipts if r.get("run_id")!=current]
    result=inspect(stable,args.source_sha)
    result=verify_actions_conclusions(
        result,stable,args.repo,current_run_id=current)
    result=verify_recent_schedule_health(
        result,args.repo,current_run_id=current)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "status":result["status"],
        "recorded_scheduled_runs":result["recorded_scheduled_runs"],
        "actions_runs_verified":result.get("actions_runs_verified",False),
        "automatic_shard_increase_authorized":False,
        "trade_gate":"BLOCKED"
    }))


if __name__=="__main__":
    main()
