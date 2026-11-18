"""Current 242+ P2 missing-feature triage joined with existing seven P3 links.

No synthetic bars, no issuer links added, no official PDF authenticity claim.
The current full SHA replay and immutable 241 baseline must both agree on the
EXACT 16 affected original CSV identities before legacy P3 link reuse.
"""
import argparse,copy,json
from pathlib import Path
from collector.p2_original_gap_action_triage import triage as historical_triage
from collector.p3_three_issuer_halt_source_crosswalk import crosswalk
from collector.p3_four_issuer_st_crosswalk import reconcile as crosswalk_st

PHASE="P2_P3_LIVE_FEATURE_GAP_AND_ISSUER_DISCLOSURE_RESEARCH_QUEUE"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
def join(live,replayed,first,second):
    if (not isinstance(live,dict) or not isinstance(replayed,dict)
        or live!=replayed or live.get("source_epoch_sha256")!=EPOCH
        or live.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
        or live.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
        or type(live.get("checkpoint_completed_shards")) is not int
        or live["checkpoint_completed_shards"]<242
        or live.get("archived_original_shards")!=live["checkpoint_completed_shards"]
        or live.get("observed_archived_shards")!=live["checkpoint_completed_shards"]
        or live.get("unobserved_archived_shards")!=0
        or live.get("feature_complete_shards")!=live["checkpoint_completed_shards"]-15
        or live.get("observed_with_feature_gaps_shards")!=15
        or live.get("issuer_evidence_gap_count")!=16
        or live.get("gap_reason_counts")!={"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":16}
        or live.get("trade_gate")!="BLOCKED"
        or live.get("historical_PIT_verified") is not False
        or live.get("coverage_certified_for_trading") is not False
        or live.get("orders")!=[] or live.get("executable_candidates")!=[]):
        raise ValueError("live SHA-replayed source diverges or overpromotes research")
    # Preserve the full queue and its issuer hashes while adapting the old
    # 241-shard triage's count-only historical fixture, without changing it.
    legacy=copy.deepcopy(live)
    legacy["checkpoint_completed_shards"]=241
    legacy["observed_archived_shards"]=241
    legacy["feature_complete_shards"]=226
    historical=historical_triage(legacy)
    three=crosswalk(historical,first)
    four=crosswalk_st(historical,second)
    references=set(three["referenced_issuers"])|set(four["issuer_results"])
    if len(references)!=7:
        raise ValueError("overlapping or missing curated issuer references")
    issues=historical["research_actions"]
    susp=[x for x in issues if x["category"]=="VENDOR_SUSPENDED_IN_LAST_21_ROWS"]
    ipo=[x for x in issues if x["category"]=="FEWER_THAN_21_VENDOR_ROWS_ASOF"]
    unlinked=[x for x in susp if x["issuer"] not in references]
    if (len(issues)!=16 or len(susp)!=15 or len(ipo)!=1
        or len(unlinked)!=8 or set(references)-{x["issuer"] for x in susp}):
        raise ValueError("P3 reference join not exactly reconciled")
    return {
        "phase":PHASE,
        "source_epoch_sha256":EPOCH,
        "current_same_epoch_original_shards":live["checkpoint_completed_shards"],
        "current_replayed_feature_complete_shards":live["feature_complete_shards"],
        "current_coverage_pct":round(100*live["feature_complete_shards"]/live["checkpoint_completed_shards"],2),
        "unresolved_feature_gap_shards":15,
        "unresolved_gap_issuers":16,
        "vendor_suspension_issuer_count":15,
        "short_ipo_history_issuer_count":1,
        "curated_p3_reference_issuer_count":7,
        "official_pdf_original_sha_certified_issuer_count":0,
        "missing_p3_halt_source_reference_issuer_count":8,
        "existing_p3_reference_issuers":sorted(references),
        "missing_official_halt_source_research_queue":[{
            "issuer":x["issuer"],"shard_id":x["shard_id"],
            "original_csv_sha256":x["original_csv_sha256"],
            "vendor_suspended_rows_last_21":x["suspended_rows_last_21"],
            "next_research_action":"FIND_ISSUER_DATED_HALT_RESUME_DISCLOSURES",
            "source_verified_officially":False,
            "link_found":False,
            "gap_resolved":False
        } for x in sorted(unlinked,key=lambda x:x["issuer"])],
        "short_ipo_history_research_queue":[{
            "issuer":x["issuer"],"shard_id":x["shard_id"],
            "original_csv_sha256":x["original_csv_sha256"],
            "next_research_action":"VERIFY_EXCHANGE_LISTING_DAY_AND_NO_FAKE_BACKFILL",
            "gap_resolved":False
        } for x in ipo],
        "independent_csv_sha_replay_required_first":True,
        "all_known_gap_source_csv_shas_reconciled_with_curated_references":True,
        "issuer_pdf_bytes_sha_verified":False,
        "complete_exchange_halt_pit_calendar_verified":False,
        "feature_shards_promoted":0,
        "trading_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    for name in ("live","replayed","three","four","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    read=lambda key:json.loads(getattr(a,key).read_text())
    out=join(*(read(k) for k in ("live","replayed","three","four")))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("P2_P3_LIVE_RECONCILED_GAP_RESEARCH_QUEUE",
          json.dumps({k:out[k] for k in ("current_same_epoch_original_shards",
          "current_replayed_feature_complete_shards",
          "curated_p3_reference_issuer_count",
          "missing_p3_halt_source_reference_issuer_count",
          "trade_gate")}))
if __name__=="__main__":main()
