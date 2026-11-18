"""P1 schedule creation lag and accepted-shard evidence by real GitHub run.

Read-only, bounded to an explicit fresh Actions run page. Source receipts are
fetched separately and must pass existing post-conclusion SHA reconciliation.
The resulting total is *sample verified accepted shards*, NOT a change from
the current active checkpoint or proof that unobserved schedules ran.
"""
import argparse
import base64
import json
import re
import subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path

from collector.p1_schedule_final_attestation import verify
from collector.p1_schedule_run_provenance import nominal, parse_utc
from collector.p1_live_schedule_archive_health import TARGET,title_matches_event,EPOCH
from collector.p1_checkpoint import validate as validate_checkpoint

PHASE="P1_OBSERVED_SCHEDULE_LATENCY_AND_DURABLE_SHARD_ATTESTATION"
SOURCE_PATH="evidence/schedule_runs/"+EPOCH[:16]+"/run_{run_id}_attempt_{attempt}.json"
MAX_RUNS=50
MAX_RECEIPTS=20

def review(api,receipts,checkpoint,now):
    validate_checkpoint(checkpoint)
    if checkpoint["source_sha256"]!=EPOCH or checkpoint["completed_shards"]<241:
        raise ValueError("wrong current active ledger, no cross-epoch aggregation")
    if (not isinstance(api,dict) or not isinstance(api.get("workflow_runs"),list)
        or len(api["workflow_runs"])>MAX_RUNS
        or type(api.get("total_count")) is not int
        or api["total_count"]<len(api["workflow_runs"])
        or not isinstance(receipts,dict)
        or len(receipts)>MAX_RECEIPTS):
        raise ValueError("invalid or unbounded live Actions evidence")
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("UTC observation required")
    now=now.astimezone(timezone.utc)
    cutoff=now-timedelta(hours=24)
    chosen=[]
    for run in api["workflow_runs"]:
        if not isinstance(run,dict):
            raise ValueError("malformed GitHub run")
        if (run.get("path")!=TARGET or run.get("head_branch")!="main"
            or run.get("event") not in ("schedule","workflow_dispatch","push")
            or not title_matches_event(run)):
            raise ValueError("wrong workflow or untrusted origin")
        created=parse_utc(run.get("created_at"))
        if created>now:raise ValueError("future GitHub run")
        if created>=cutoff:
            chosen.append(run)
    if len(chosen)>MAX_RECEIPTS:
        raise ValueError("recent P1 run count exceeds bounded coverage")
    ids=[r.get("id") for r in chosen]
    if (any(type(i) is not int or i<=0 for i in ids)
        or len(ids)!=len(set(ids))
        or set(receipts)-set(map(str,ids))):
        raise ValueError("run-bound receipts not in selected run cohort")
    result=[]
    accepted_indices=set()
    for run in sorted(chosen,key=lambda x:(x["created_at"],x["id"])):
        rid=run["id"]
        state=run.get("status")
        conclusion=run.get("conclusion")
        row={
            "run_id":rid,"trigger":run["event"],
            "created_at_utc":parse_utc(run["created_at"]).isoformat(),
            "workflow_final_conclusion":conclusion if state=="completed" else None,
            "scheduled_creation_lag_minutes":None,
            "creation_delay_class":"NOT_ESTABLISHED",
            "sampled_original_shards_accepted":None,
            "validated_source_shard_indices":[],
            "durable_sha_lineage_verified":False,
            "source_receipt_status":"NOT_AVAILABLE_OR_NOT_APPLICABLE",
        }
        if run["event"]=="schedule":
            title=run["name"]
            if not title.startswith("P1 origin ") or not title.endswith(" [NO TRADES]"):
                raise ValueError("scheduled run missing exact literal cron title")
            cron=title[len("P1 origin "):-len(" [NO TRADES]")]
            planned,delay=nominal(cron,parse_utc(run["created_at"]))
            row["literal_cron_utc"]=cron
            row["inferred_nominal_slot_utc"]=planned.isoformat()
            row["scheduled_creation_lag_minutes"]=delay
            row["creation_delay_class"]=(
                "SEVERE_OVER_3H" if delay>180 else
                "LATE_OVER_45M" if delay>45 else "WITHIN_45M")
            receipt=receipts.get(str(rid))
            if receipt is not None:
                attested=verify(run,receipt,checkpoint)
                row["source_receipt_status"]=attested["state"]
                if attested.get("per_shard_manifest_and_receipt_sha_matched") is True and attested.get("final_actions_success_authenticated") is True:
                    indices=attested["accepted_source_shard_indices"]
                    if set(indices)&accepted_indices:
                        raise ValueError("duplicate accepted shard across source runs")
                    accepted_indices.update(indices)
                    row["validated_source_shard_indices"]=indices
                    row["sampled_original_shards_accepted"]=len(indices)
                    row["durable_sha_lineage_verified"]=True
                elif attested["state"]=="SCHEDULE_SUCCESS_NO_NEW_ARCHIVED_SHARDS":
                    row["sampled_original_shards_accepted"]=0
                    row["durable_sha_lineage_verified"]=True
        result.append(row)
    scheduled=[r for r in result if r["trigger"]=="schedule"]
    proven=[r for r in scheduled if r["durable_sha_lineage_verified"]]
    delays=[r["scheduled_creation_lag_minutes"] for r in scheduled]
    bucket={k:sum(r["creation_delay_class"]==k for r in scheduled) for k in (
        "WITHIN_45M","LATE_OVER_45M","SEVERE_OVER_3H")}
    return {
        "phase":PHASE,
        "active_source_epoch_sha256":EPOCH,
        "active_completed_shards":checkpoint["completed_shards"],"active_total_shards":checkpoint["shard_count"],
        "recent_24h_workflow_runs":len(result),
        "recent_24h_scheduled_runs":len(scheduled),
        "scheduled_creation_lag_bucket_counts":bucket,
        "scheduled_creation_lag_minutes_max":max(delays) if delays else None,
        "scheduled_creation_lag_minutes_min":min(delays) if delays else None,
        "scheduled_runs_with_final_sha_attestation":len(proven),
        "final_verified_source_run_shards_sample_total":sum(
            r["sampled_original_shards_accepted"] for r in proven),
        "not_derived_as_new_since_current_checkpoint":True,
        "unattested_scheduled_runs":len(scheduled)-len(proven),
        "workflow_listing_may_be_truncated":api["total_count"]>len(api["workflow_runs"]),
        "runs":result,
        "github_created_at_is_runner_start":False,
        "inferred_nominal_slot_is_authenticated":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "automatic_recovery_dispatch_authorized":False,
        "production_writer_cutover_authorized":False,
    }

def main():
    ap=argparse.ArgumentParser()
    for name in ("runs","receipts","checkpoint","out"):
        ap.add_argument("--"+name,required=True,type=Path)
    args=ap.parse_args()
    read=lambda p:json.loads(p.read_text())
    result=review(read(args.runs),read(args.receipts),read(args.checkpoint),datetime.now(timezone.utc))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("P1_RUN_LATENCY_AND_DURABLE_DELTAS",json.dumps({
       k:result[k] for k in ("recent_24h_workflow_runs",
       "recent_24h_scheduled_runs","scheduled_creation_lag_bucket_counts",
       "scheduled_runs_with_final_sha_attestation",
       "final_verified_source_run_shards_sample_total",
       "unattested_scheduled_runs","trade_gate")
    },ensure_ascii=False))
if __name__=="__main__":
    main()
