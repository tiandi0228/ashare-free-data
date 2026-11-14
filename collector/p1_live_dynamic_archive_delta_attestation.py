"""Live P1 pinned epoch delta attestation beyond the fixed 241-shard baseline.

Cross-checks final GitHub Actions success, run-specific source receipt SHA,
current main checkpoint and actual original-archive shard membership. The
snapshot is fetched read-only in CI. No source writes or trading authorization.
"""
import argparse
import json
from pathlib import Path
from collector.p1_schedule_final_attestation import verify
from collector.p1_checkpoint import validate as validate_checkpoint

PHASE="P1_LIVE_CURRENT_EPOCH_RUN_DELTA_AND_ORIGINAL_ARCHIVE_ATTESTATION"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
BASELINE=241
def attest(run,receipt,checkpoint,archive):
    validate_checkpoint(checkpoint)
    if (checkpoint.get("source_sha256")!=EPOCH
        or type(checkpoint.get("completed_shards")) is not int
        or checkpoint["completed_shards"]<BASELINE
        or checkpoint.get("trade_gate")!="BLOCKED"
        or not isinstance(archive,dict)
        or archive.get("source_sha256")!=EPOCH
        or archive.get("trade_gate")!="BLOCKED"
        or not isinstance(archive.get("archived_shards"),list)):
        raise ValueError("active original archive source epoch or safety mismatch")
    completed={x["index"] for x in checkpoint["completed"]}
    archived=archive["archived_shards"]
    if (len(archived)!=checkpoint["completed_shards"]
        or len(set(archived))!=len(archived)
        or any(type(i) is not int for i in archived)
        or set(archived)!=completed):
        raise ValueError("checkpoint/archive shard identity diverged")
    verified=verify(run,receipt,checkpoint)
    if (verified.get("state")!="SCHEDULE_SUCCESS_AND_DURABLE_SHARDS_CONFIRMED"
        or verified.get("source_sha256")!=EPOCH
        or verified.get("per_shard_manifest_and_receipt_sha_matched") is not True
        or verified.get("final_actions_success_authenticated") is not True
        or verified.get("trade_gate")!="BLOCKED"
        or verified.get("orders")!=[] or verified.get("executable_candidates")!=[]):
        raise ValueError("final source run or per-shard digest not independently proven")
    accepted=verified["accepted_source_shard_indices"]
    if not set(accepted).issubset(set(archived)):
        raise ValueError("source run accepted shard not in original archive")
    return {
        "phase":PHASE,
        "source_epoch_sha256":EPOCH,
        "historical_checkpoint_baseline":BASELINE,
        "live_completed_shards":checkpoint["completed_shards"],
        "live_total_shards":checkpoint["shard_count"],
        "live_coverage_pct":round(100*checkpoint["completed_shards"]/checkpoint["shard_count"],2),
        "shards_remaining":checkpoint["shard_count"]-checkpoint["completed_shards"],
        "confirmed_original_archived_shards":len(archived),
        "source_run_id":verified["run_id"],
        "source_final_success_authenticated":True,
        "source_run_before":verified["source_checkpoint_before"],
        "source_run_after":verified["source_checkpoint_after"],
        "source_run_new_shards":verified["durably_accepted_shards_in_source_run"],
        "source_run_shard_indices":accepted,
        "source_run_sha_receipts_verified":True,
        "current_checkpoint_delta_above_baseline":checkpoint["completed_shards"]-BASELINE,
        "source_run_increment_already_in_checkpoint":True,
        "new_live_bytes_replayed_in_this_step":False,
        "new_shard_is_historical_PIT_certified":False,
        "writer_change_authorized":False,
        "production_prewrite_gate_deployed":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("run","receipt","checkpoint","archive","out"):
        p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args()
    read=lambda k:json.loads(getattr(args,k).read_text())
    out=attest(*(read(k) for k in ("run","receipt","checkpoint","archive")))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:out[k] for k in ("live_completed_shards","live_total_shards",
        "source_run_id","source_run_new_shards","source_run_shard_indices",
        "trade_gate")},ensure_ascii=False))
if __name__=="__main__":main()
