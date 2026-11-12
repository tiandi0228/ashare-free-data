"""P1 operational ingestion health from live Actions metadata and pinned ledger.

Read-only. Success of a source job, even with a 'persist' commit, is NOT
proof of more archived shards until original bytes and full lineage replay.
"""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from collector.p1_current_progress import report as validate_active
from collector.p1_checkpoint import validate as validate_ledger

PHASE="P1_LIVE_RUN_HEALTH_VS_PINNED_ACTIVE_ARCHIVE_COVERAGE"
TARGET=".github/workflows/p1-fresh-vendor-roster.yml"
WORKFLOW_NAME="P1 fresh Baostock mainboard roster observation (NO TRADES)"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
FINAL={"success","failure","cancelled","timed_out","neutral","skipped","action_required","stale"}
ACTIVE={"queued","in_progress","requested","waiting","pending"}

def audit(lock,checkpoint,archive,runs,now_utc):
    current=validate_active(lock,checkpoint)
    if (current["source_sha256"]!=EPOCH
        or current["completed_shards"]!=241
        or current["total_shards"]!=400
        or current["completed_issuers"]!=1922
        or not isinstance(archive,dict)
        or archive.get("source_sha256")!=EPOCH
        or archive.get("trade_gate")!="BLOCKED"
        or not isinstance(archive.get("archived_shards"),list)
        or len(archive["archived_shards"])!=241
        or set(archive["archived_shards"])!={x["index"] for x in checkpoint["completed"]}):
        raise ValueError("P1 pinned source and archive are not reconciled")
    if (not isinstance(runs,dict)
        or type(runs.get("total_count")) is not int
        or runs["total_count"]<0
        or not isinstance(runs.get("workflow_runs"),list)):
        raise ValueError("missing GitHub Actions run results")
    entries=runs["workflow_runs"]
    if len(entries)>50 or runs["total_count"]<len(entries):
        raise ValueError("truncated or invalid run page")
    if not isinstance(now_utc,datetime) or now_utc.tzinfo is None:
        raise ValueError("UTC observation time required")
    now=now_utc.astimezone(timezone.utc)
    seen=set();info=[]
    for x in entries:
        if not isinstance(x,dict):
            raise ValueError("invalid workflow run object")
        run_id=x.get("id")
        if type(run_id) is not int or run_id<=0 or run_id in seen:
            raise ValueError("duplicate/invalid run ID")
        seen.add(run_id)
        if (x.get("path")!=TARGET or x.get("name")!=WORKFLOW_NAME
            or x.get("head_branch")!="main"
            or x.get("event") not in ("schedule","workflow_dispatch","push")):
            raise ValueError("wrong P1 workflow or execution context")
        try:
            created=datetime.fromisoformat(x["created_at"].replace("Z","+00:00"))
        except (KeyError,ValueError,TypeError,AttributeError) as exc:
            raise ValueError("invalid Actions created time") from exc
        if created.tzinfo is None or created.astimezone(timezone.utc)>now:
            raise ValueError("future Actions run timestamp")
        status=x.get("status")
        conclusion=x.get("conclusion")
        if (status not in ACTIVE|{"completed"}
            or (status=="completed" and conclusion not in FINAL)
            or (status in ACTIVE and conclusion is not None)):
            raise ValueError("contradictory Actions conclusion")
        info.append({
            "run_id":run_id,"event":x["event"],
            "created_at_utc":created.astimezone(timezone.utc).isoformat(),
            "status":status,"conclusion":conclusion,
            "fresh_within_24h":(now-created.astimezone(timezone.utc)).total_seconds()<=86400,
        })
    info.sort(key=lambda x:(x["created_at_utc"],x["run_id"]),reverse=True)
    recent=[x for x in info if x["fresh_within_24h"]]
    latest=info[0] if info else None
    pending=[x for x in info if x["status"] in ACTIVE]
    return {
        "phase":PHASE,
        "active_p1_source_sha256":EPOCH,
        "active_completed_shards":241,
        "active_total_shards":400,
        "active_coverage_pct":60.25,
        "active_original_archive_membership_confirmed":True,
        "active_issuer_count":1922,
        "remaining_shards":159,
        "last_actions_run":latest,
        "recent_24h_runs":len(recent),
        "recent_24h_successful_runs":sum(x["conclusion"]=="success" for x in recent),
        "recent_24h_failed_or_cancelled_runs":sum(x["status"]=="completed" and x["conclusion"]!="success" for x in recent),
        "active_or_queued_run_ids":[x["run_id"] for x in pending],
        "listed_workflow_run_count":len(info),
        "remote_reported_total_run_count":runs["total_count"],
        "run_list_complete":runs["total_count"]<=len(info),
        "latest_run_provenance_disproves_stale_checkpoint":False,
        "new_shards_from_run_history":None,
        "new_shards_since_current_checkpoint":None,
        "archived_original_csv_replay_this_step":False,
        "production_writer_cutover_authorized":False,
        "recovery_dispatch_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("lock","checkpoint","archive","runs","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    def load(x):return json.loads(x.read_text())
    result=audit(load(a.lock),load(a.checkpoint),load(a.archive),load(a.runs),datetime.now(timezone.utc))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
        "active_completed_shards","active_total_shards","recent_24h_runs",
        "recent_24h_successful_runs","active_or_queued_run_ids",
        "last_actions_run","new_shards_from_run_history","trade_gate")},ensure_ascii=False))
if __name__=="__main__":main()
