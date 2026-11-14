"""Read-only acceptance of a LIVE P2 full original-CSV and receipts replay.

This is deliberately distinct from the fixed 226/241 historical snapshot.
The replay producer must independently validate every CSV's SHA and receipt;
we only certify its evidence consistency with the same-epoch live heads.
No PIT, stock recommendations, order generation, or private write access.
"""
import argparse
import json
import re
from pathlib import Path
from collector.p1_checkpoint import validate as validate_checkpoint

PHASE="P2_LIVE_242_OR_MORE_ORIGINAL_SHA_RECEIPT_REPLAY_RECONCILIATION"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
MIN_SHARDS=241
GIT_SHA=re.compile(r"[0-9a-f]{40}\Z")
COMPARED=(
    "phase","status","source_epoch_sha256",
    "checkpoint_completed_shards","checkpoint_total_shards",
    "archived_original_shards","coverage_report_count",
    "observed_archived_shards","feature_complete_shards",
    "observed_with_feature_gaps_shards","unobserved_archived_shards",
    "observed_shard_ids","unobserved_shard_ids","gap_shard_ids",
    "feature_issuer_count","issuer_evidence_gap_count",
    "observed_feature_or_gap_issuers","unobserved_issuer_count",
    "gap_reason_counts","gap_issuer_codes","gap_repair_queue",
    "full_archive_evidence_accounted","full_archive_feature_coverage",
    "trade_gate","orders","executable_candidates","historical_PIT_verified",
    "coverage_certified_for_trading","full_market_universe_verified",
)
def reconcile(replayed,published,checkpoint,archive,refs):
    validate_checkpoint(checkpoint)
    if (not isinstance(replayed,dict) or not isinstance(published,dict)
        or not isinstance(archive,dict) or not isinstance(refs,dict)
        or any(not isinstance(refs.get(name),str) or not GIT_SHA.fullmatch(refs[name])
               for name in ("checkpoint","original_csv_archive","feature_receipts"))):
        raise ValueError("missing source git commit provenance")
    count=checkpoint["completed_shards"]
    archived=archive.get("archived_shards")
    if (checkpoint["source_sha256"]!=EPOCH or count<MIN_SHARDS
        or checkpoint["shard_count"]!=400 or checkpoint["trade_gate"]!="BLOCKED"
        or archive.get("source_sha256")!=EPOCH or archive.get("trade_gate")!="BLOCKED"
        or not isinstance(archived,list) or len(archived)!=count
        or len(set(archived))!=len(archived)
        or any(type(x) is not int for x in archived)
        or set(archived)!={x["index"] for x in checkpoint["completed"]}):
        raise ValueError("live original CSV archive diverges from same-epoch P1 checkpoint")
    for name,data in (("replayed",replayed),("published",published)):
        if (data.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
            or data.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            or data.get("source_epoch_sha256")!=EPOCH
            or data.get("checkpoint_completed_shards")!=count
            or data.get("archived_original_shards")!=count
            or data.get("observed_archived_shards")!=count
            or data.get("unobserved_archived_shards")!=0
            or data.get("full_archive_evidence_accounted") is not True
            or data.get("full_archive_feature_coverage") is not False
            or data.get("trade_gate")!="BLOCKED"
            or data.get("historical_PIT_verified") is not False
            or data.get("coverage_certified_for_trading") is not False
            or data.get("full_market_universe_verified") is not False
            or data.get("orders")!=[] or data.get("executable_candidates")!=[]
            or type(data.get("coverage_report_count")) is not int
            or data["coverage_report_count"]<1):
            raise ValueError(name+" unsupported source or certification claim")
        if (type(data.get("feature_complete_shards")) is not int
            or type(data.get("observed_with_feature_gaps_shards")) is not int
            or data["feature_complete_shards"]+data["observed_with_feature_gaps_shards"]!=count):
            raise ValueError(name+" feature+gap shard identity mismatch")
        if (type(data.get("observed_feature_or_gap_issuers")) is not int
            or data["observed_feature_or_gap_issuers"]!=checkpoint["completed_issuers"]):
            raise ValueError(name+" issuer count does not match original checkpoint")
    disagreement=[key for key in COMPARED if replayed.get(key)!=published.get(key)]
    if disagreement:
        raise ValueError("LIVE_FULL_REPLAY_MISMATCH "+",".join(disagreement))
    return {
        "phase":PHASE,
        "source_epoch_sha256":EPOCH,
        "accepted_main_shards":count,
        "source_total_shards":checkpoint["shard_count"],
        "P1_coverage_pct":round(100*count/checkpoint["shard_count"],2),
        "P2_feature_complete_shards":replayed["feature_complete_shards"],
        "P2_observed_original_shards":count,
        "P2_feature_coverage_pct":round(100*replayed["feature_complete_shards"]/count,2),
        "unresolved_feature_gap_shards":replayed["observed_with_feature_gaps_shards"],
        "unresolved_issuer_gap_count":replayed["issuer_evidence_gap_count"],
        "feature_receipts_replayed":replayed["coverage_report_count"],
        "same_epoch_original_archived_shards_verified":True,
        "independent_replayed_feature_summary_matches_published":True,
        "replay_comparison_fields":len(COMPARED),
        "input_git_head_commits":refs,
        "original_vendor_csv_not_historical_PIT_certified":True,
        "full_market_universe_verified":False,
        "historical_PIT_verified":False,
        "orders":[],"executable_candidates":[],"trade_gate":"BLOCKED",
        "no_data_written_or_overwritten":True,
        "cutover_authorized":False,
        "trading_authorized":False,
    }

def main():
    p=argparse.ArgumentParser()
    for key in ("replayed","published","checkpoint","archive","out"):
        p.add_argument("--"+key,type=Path,required=True)
    for key in ("checkpoint","original_csv_archive","feature_receipts"):
        p.add_argument("--"+key.replace("_","-")+"-git-sha",required=True)
    a=p.parse_args()
    read=lambda key:json.loads(getattr(a,key).read_text())
    result=reconcile(*(read(k) for k in ("replayed","published","checkpoint","archive")),
        {k:getattr(a,k+"_git_sha") for k in ("checkpoint","original_csv_archive","feature_receipts")})
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("P2_LIVE_SHA_REPLAY_ACCEPTED",json.dumps({
        k:result[k] for k in ("accepted_main_shards","P2_feature_complete_shards",
        "P2_feature_coverage_pct","unresolved_feature_gap_shards",
        "feature_receipts_replayed","trade_gate")},ensure_ascii=False))
if __name__=="__main__":
    main()
