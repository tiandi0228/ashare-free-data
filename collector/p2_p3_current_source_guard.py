"""Fail-closed provenance guard for dynamic P2/P3 research artifact crosswalks.

Checks that the latest persisted P2 source and independently saved P3
full-P1 research queue use the same frozen source roster epoch. P3 event
text can cover older epochs, but is never official status evidence.
"""
import argparse,json,re
from pathlib import Path

SHA=re.compile(r"[0-9a-f]{64}\Z")
ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")


def validate_sources(gaps,coverage,queue,source_p2_run,source_p3_run):
    if (type(source_p2_run) is not int or source_p2_run<=0 or
        type(source_p3_run) is not int or source_p3_run<=0):
        raise ValueError("invalid completed source Actions run IDs")
    if (not isinstance(gaps,dict) or not isinstance(coverage,dict) or
        not isinstance(queue,dict)):
        raise ValueError("missing research provenance")
    epoch=coverage.get("source_epoch_sha256")
    if (not isinstance(epoch,str) or not SHA.fullmatch(epoch)
        or gaps.get("source_epoch_sha256")!=epoch
        or queue.get("roster_source_sha256")!=epoch):
        raise ValueError("stale or cross-epoch P2/P3 provenance")
    if (coverage.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
        or coverage.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
        or coverage.get("trade_gate")!="BLOCKED"
        or coverage.get("orders")!=[]
        or coverage.get("historical_PIT_verified") is not False
        or coverage.get("coverage_certified_for_trading") is not False
        or coverage.get("full_archive_evidence_accounted") is not True
        or coverage.get("unobserved_archived_shards")!=0
        or coverage.get("unobserved_issuer_count")!=0):
        raise ValueError("P2 durable research coverage is unsafe or incomplete")
    codes=coverage.get("gap_issuer_codes")
    results=gaps.get("results")
    if (not isinstance(codes,list) or not isinstance(results,list)
        or len(codes)>3200 or codes!=sorted(set(codes))
        or any(not isinstance(x,str) or not ISSUER.fullmatch(x) for x in codes)
        or len(codes)!=coverage.get("issuer_evidence_gap_count")
        or len(results)!=gaps.get("research_gap_issuers")
        or len(results)!=len(codes)
        or gaps.get("phase")!="P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS"
        or gaps.get("status")!="SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY"
        or gaps.get("trade_gate")!="BLOCKED"
        or gaps.get("orders")!=[]
        or gaps.get("historical_PIT_verified") is not False
        or gaps.get("coverage_gaps_resolved")!=0
        or gaps.get("historical_halt_intervals_certified")!=0):
        raise ValueError("stale or damaged P2 original gap diagnosis")
    reported=[x.get("issuer") if isinstance(x,dict) else None for x in results]
    if sorted(reported,key=lambda x: str(x))!=codes:
        raise ValueError("P2 gap issuers differ from latest durable ledger")
    if (queue.get("trade_gate")!="BLOCKED"
        or queue.get("orders")!=[]
        or queue.get("historical_PIT_verified") is not False):
        # P3 P1 research queue does not authenticate exchange histories.
        raise ValueError("unsafe P3 historical source queue")
    return {
        "phase":"P2_P3_CURRENT_RESEARCH_SOURCE_CROSSWALK_GUARD",
        "status":"SAME_P1_EPOCH_SOURCE_BOUNDED_RESEARCH_ONLY",
        "source_epoch_sha256":epoch,
        "p2_source_run_id":source_p2_run,
        "p3_source_run_id":source_p3_run,
        "p2_current_archived_shards":coverage.get("observed_archived_shards"),
        "p2_vendor_gap_issuers":len(codes),
        "issuer_codes":codes,
        "P3_event_text_is_official_halt_authentication":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    for arg in ("p2-gaps","p2-coverage","p3-queue","out"):
        p.add_argument("--"+arg,type=Path,required=True)
    p.add_argument("--p2-run",type=int,required=True)
    p.add_argument("--p3-run",type=int,required=True)
    a=p.parse_args()
    result=validate_sources(json.loads(a.p2_gaps.read_text()),
        json.loads(a.p2_coverage.read_text()),
        json.loads(a.p3_queue.read_text()),a.p2_run,a.p3_run)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
        "status","p2_source_run_id","p3_source_run_id",
        "p2_current_archived_shards","p2_vendor_gap_issuers","trade_gate")},ensure_ascii=False))


if __name__=="__main__":
    main()
