"""Fail-closed P0/P1 source-epoch-aware progress report (NO TRADES).

P0 historical 100% is explicitly a previously reported development claim,
not a fresh current production acceptance. Active P1 is determined ONLY by
the actual pinned roster SHA, never by legacy alias or maximum counters.
The companion P2 full CSV/receipt replay proves archived original content.
"""
import argparse
import json
from pathlib import Path

from collector.p1_current_progress import report as p1_report
from collector.p1_checkpoint import validate as validate_ledger

PHASE="STOCKMATE_P0_P1_ACTIVE_EPOCH_AND_HISTORICAL_CLAIM_RECONCILIATION"
EXPECTED_EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
P2_PHASE="P2_CURRENT_SAME_EPOCH_ORIGINAL_CSV_FULL_REPLAY"

def reconcile(lock,active,legacy,archive_status,p2_replay,offline_ok):
    if offline_ok is not True:
        raise ValueError("P0 selected offline tests not verified this run")
    current=p1_report(lock,active)
    validate_ledger(legacy)
    if (current["source_sha256"]!=EXPECTED_EPOCH
        or current["completed_shards"]!=241
        or current["total_shards"]!=400
        or current["completed_issuers"]!=1922
        or legacy["source_sha256"]==current["source_sha256"]
        or legacy["completed_shards"]!=44
        or legacy["shard_count"]!=400):
        raise ValueError("active and legacy roster epochs mixed or changed")
    completed={r["index"] for r in active["completed"]}
    archived=archive_status.get("archived_shards")
    if (archive_status.get("source_sha256")!=EXPECTED_EPOCH
        or archive_status.get("trade_gate")!="BLOCKED"
        or not isinstance(archived,list)
        or len(archived)!=241
        or any(type(i) is not int for i in archived)
        or len(set(archived))!=241
        or set(archived)!=completed):
        raise ValueError("original archived shard membership mismatch")
    if (not isinstance(p2_replay,dict)
        or p2_replay.get("phase")!=P2_PHASE
        or p2_replay.get("source_epoch_sha256")!=EXPECTED_EPOCH
        or p2_replay.get("observed_archived_shards")!=241
        or p2_replay.get("feature_complete_shards")!=226
        or p2_replay.get("previous_summary_and_full_original_replay_match") is not True
        or p2_replay.get("original_CSVs_independently_replayed_in_this_run") is not True
        or p2_replay.get("trade_gate")!="BLOCKED"
        or p2_replay.get("orders")!=[]
        or p2_replay.get("executable_candidates")!=[]
        or p2_replay.get("historical_PIT_verified") is not False):
        raise ValueError("archived CSV and P2 feature replay insufficient")
    return {
        "phase":PHASE,
        "P0":{
            "historical_development_pct_reported":100,
            "historical_development_label":"PREVIOUSLY_REPORTED_NOT_REACCEPTED_AS_PRODUCTION",
            "selected_offline_test_modules_passing_in_this_run":True,
            "current_full_production_acceptance_pct":None,
            "current_real_quote_freshness_15s_certified":False,
            "current_complete_intraday_minute_source_certified":False,
            "production_approved":False,
        },
        "P1":{
            "source_selection":"PINNED_ACTIVE_ROSTER_NOT_LEGACY_ALIAS",
            "active_source_sha256":EXPECTED_EPOCH,
            "active_completed_shards":241,
            "active_total_shards":400,
            "active_coverage_pct":60.25,
            "active_completed_issuers":1922,
            "active_roster_issuers":3194,
            "original_archive_shard_membership_verified":True,
            "original_CSV_replay_verified_in_this_run":True,
            "legacy_alias_source_sha256":legacy["source_sha256"],
            "legacy_alias_completed_shards":44,
            "legacy_alias_total_shards":400,
            "legacy_alias_is_active_source":False,
            "cross_epoch_addition_authorized":False,
            "full_historical_official_market_coverage_certified":False,
            "private_repository_migration_verified":False,
            "production_writer_cutover_authorized":False,
        },
        "P2_research_feature_complete_shards":226,
        "P2_research_observed_shards":241,
        "P2_research_feature_coverage_pct":round(226/241*100,2),
        "historical_PIT_verified":False,
        "full_P0_to_P4_project_completion_pct":None,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    for key in ("lock","active","legacy","archive-status","p2-replay","out"):
        p.add_argument("--"+key,required=True,type=Path)
    p.add_argument("--p0-offline-ok",action="store_true")
    a=p.parse_args()
    def load(path):return json.loads(path.read_text())
    result=reconcile(load(a.lock),load(a.active),load(a.legacy),
                     load(a.archive_status),load(a.p2_replay),a.p0_offline_ok)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "P0_historical_development_pct":100,
        "P0_current_production_acceptance_pct":None,
        "P1_active_completed_shards":241,
        "P1_active_total_shards":400,
        "P1_active_coverage_pct":60.25,
        "P1_legacy_alias_completed_shards":44,
        "P2_feature_complete_shards":226,
        "trade_gate":"BLOCKED",
    },ensure_ascii=False))
if __name__=="__main__":main()
