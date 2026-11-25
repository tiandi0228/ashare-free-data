"""P2 independently replayed original-gap triage: never fabricate vendor trading bars.

Classify reason from SHA-replayed durable same-epoch feature summary only.
A 21-observation window with supplier suspension rows is not an official SSE
halt certification; a short observed window is not automatically a data error.
"""
import argparse
import json
import re
from pathlib import Path

EPOCH = "5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
SHA = re.compile(r"[0-9a-f]{64}\Z")
CODE = re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
SHARD = re.compile(r"shard_[0-9]{4}\Z")
PHASE = "P2_ORIGINAL_SHA_VERIFIED_FEATURE_GAP_RESEARCH_TRIAGE"

def triage(source):
    if (not isinstance(source, dict)
        or source.get("phase") != "P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
        or source.get("status") != "DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
        or source.get("source_epoch_sha256") != EPOCH
        or source.get("trade_gate") != "BLOCKED"
        or source.get("historical_PIT_verified") is not False
        or source.get("coverage_certified_for_trading") is not False
        or source.get("orders") != []
        or source.get("executable_candidates") != []
        or source.get("gap_repair_queue_is_research_only") is not True):
        raise ValueError("unsafe or wrong-epoch P2 research evidence")
    count_keys = (
        "checkpoint_completed_shards","observed_archived_shards",
        "feature_complete_shards","observed_with_feature_gaps_shards",
        "unobserved_archived_shards","issuer_evidence_gap_count",
    )
    if any(type(source.get(k)) is not int or source[k] < 0 for k in count_keys):
        raise ValueError("P2 counters absent or wrong type")
    if (source["checkpoint_completed_shards"] != 241
        or source["observed_archived_shards"] != 241
        or source["feature_complete_shards"] != 226
        or source["observed_with_feature_gaps_shards"] != 15
        or source["unobserved_archived_shards"] != 0
        or source["issuer_evidence_gap_count"] != 16):
        raise ValueError("unexpected current P2 original replay counts")
    queue = source.get("gap_repair_queue")
    gap_ids = source.get("gap_shard_ids")
    if (not isinstance(queue,list) or len(queue) != 15
        or not isinstance(gap_ids,list) or len(gap_ids) != 15
        or not isinstance(source.get("gap_reason_counts"),dict)
        or source["gap_reason_counts"] != {"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":16}):
        raise ValueError("incomplete original evidence gap queue")
    result = []
    seen_shards = set()
    seen_codes = set()
    categories = {}
    for row in queue:
        if not isinstance(row,dict):
            raise ValueError("bad shard row")
        shard = row.get("shard_id")
        if not isinstance(shard,str) or not SHARD.fullmatch(shard) or shard in seen_shards:
            raise ValueError("duplicate or invalid shard")
        seen_shards.add(shard)
        items = row.get("issuer_reasons")
        if (not isinstance(items,list)
            or len(items) not in (1,2)
            or type(row.get("issuer_gap_count")) is not int
            or row["issuer_gap_count"] != len(items)):
            raise ValueError("invalid shard gap count")
        for item in items:
            if not isinstance(item,dict):
                raise ValueError("missing issuer gap")
            issuer = item.get("issuer")
            diag = item.get("original_gap_diagnostic")
            if (not isinstance(issuer,str) or not CODE.fullmatch(issuer)
                or issuer in seen_codes
                or item.get("reason") != "INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"
                or not isinstance(diag,dict)
                or diag.get("historical_PIT_verified") is not False
                or diag.get("vendor_calendar_independently_verified") is not False
                or diag.get("repair_approved") is not False
                or not isinstance(diag.get("original_csv_sha256"),str)
                or not SHA.fullmatch(diag["original_csv_sha256"])
                or diag.get("exact_asof_vendor_row_present") is not True):
                raise ValueError("unsafe or forged issuer gap evidence")
            seen_codes.add(issuer)
            history = diag.get("vendor_rows_at_or_before_asof")
            halted = diag.get("last_21_vendor_rows_suspended")
            category = diag.get("category")
            if (type(history) is not int or type(halted) is not int
                or not 0 <= halted <= min(21,history)
                or type(diag.get("first_vendor_row_day")) is not str
                or diag.get("last_vendor_row_day") != "2026-10-20"):
                raise ValueError("invalid vendor row counts or asof")
            if category == "VENDOR_SUSPENDED_IN_LAST_21_ROWS":
                if history < 21 or halted < 1:
                    raise ValueError("invalid suspended-row diagnosis")
                action = "REQUEST_OFFICIAL_HALT_STATUS_CROSSCHECK"
            elif category == "FEWER_THAN_21_VENDOR_ROWS_ASOF":
                if history >= 21 or halted != 0:
                    raise ValueError("short-history diagnosis contradicts rows")
                action = "REVIEW_LISTING_DATE_AND_NONFABRICATED_HISTORY"
            else:
                raise ValueError("unexpected or promoted feature gap category")
            categories[category] = categories.get(category,0) + 1
            result.append({
                "shard_id":shard, "issuer":issuer,
                "category":category,"vendor_rows":history,
                "suspended_rows_last_21":halted,
                "original_csv_sha256":diag["original_csv_sha256"],
                "research_action":action,
                "original_mutation_authorized":False,
                "gap_resolved":False,
                "eligible_for_feature_complete_promotion":False,
            })
    if (seen_shards != set(gap_ids)
        or len(seen_codes) != 16
        or categories != {
            "VENDOR_SUSPENDED_IN_LAST_21_ROWS":15,
            "FEWER_THAN_21_VENDOR_ROWS_ASOF":1}):
        raise ValueError("gap queue does not reconcile exactly")
    return {
        "phase":PHASE,"source_epoch_sha256":EPOCH,
        "feature_complete_shards":226,"observed_shards":241,
        "feature_coverage_pct":round(100*226/241,2),
        "unresolved_shards":15,"unresolved_issuers":16,
        "reason_counts":categories,
        "research_actions":result,
        "source_originals_replayed_before_triage":True,
        "issuer_halt_state_officially_authenticated":False,
        "history_backfill_authorized":False,
        "complete_feature_shards_promoted_by_triage":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--replayed-summary",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=triage(json.loads(a.replayed_summary.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:r[k] for k in (
        "phase","feature_complete_shards","observed_shards","unresolved_shards",
        "unresolved_issuers","reason_counts","trade_gate")},ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
