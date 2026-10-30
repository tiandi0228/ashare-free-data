"""Read-only P1 dual-pilot scaling review from permanent same-epoch GitHub receipts.

A receipt represents only one audited run. Missing or expired failed runs are
not observable here: three recorded successes permit human review, NEVER
automated scaling, PIT certification or trading.
"""
import argparse
import base64
import json
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
    decision=("RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW" if success else
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
    if not isinstance(listing,list) or len(listing)>=100:
        raise ValueError("pilot directory too large for bounded first-page review")
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
    for _,__,path in entries[:MAX_READS]:
        obj=json.loads(gh(f"repos/{repo}/contents/{path}","-f",
                          "ref=main","--method","GET"))
        if not isinstance(obj,dict) or not obj.get("sha"):
            raise ValueError("missing immutable pilot receipt blob SHA")
        data=json.loads(base64.b64decode(obj["content"]).decode())
        result.append(data)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--repo",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    receipts=load_recent_remote(args.repo,args.source_sha)
    result=inspect(receipts,args.source_sha)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "status":result["status"],
        "recorded_scheduled_runs":result["recorded_scheduled_runs"],
        "automatic_shard_increase_authorized":False,
        "trade_gate":"BLOCKED"
    }))


if __name__=="__main__":
    main()
