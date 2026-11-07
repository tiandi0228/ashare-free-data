"""Cross-run, original-CSV-checked P2 research feature coverage.

A report is only a durable *research receipt*, not an official-source attestation.
Old receipts are rechecked against current append-only archived originals.
A shard with issuer feature gaps is *observed*, not fully feature-complete.
"""
import argparse
import json
import re
from pathlib import Path

from collector.baostock_batch import END
from collector.p1_checkpoint import validate
from collector.p2_independent_bars import assess

SHA40=re.compile(r"[a-f0-9]{40}\Z")
SHARD=re.compile(r"shard_(\d{4})\Z")
PHASE="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"

def summarize(epoch,ledger,reports):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "full_market_universe_verified":False,"historical_PIT_verified":False,
          "coverage_certified_for_trading":False}
    def fail(reason):return dict(base,reason=reason)
    try:
        validate(ledger)
        epoch=Path(epoch)
        status=json.loads((epoch/"archive_status.json").read_text())
        if (epoch.name!=ledger["source_sha256"][:16]
            or status.get("source_sha256")!=ledger["source_sha256"]
            or status.get("trade_gate")!="BLOCKED"):
            return fail("EPOCH_CHECKPOINT_MISMATCH")
        ledger_indices={x["index"] for x in ledger["completed"]}
        archived={}
        for path in sorted(epoch.glob("shard_*/quality.json")):
            match=SHARD.fullmatch(path.parent.name)
            if not match:return fail("INVALID_ARCHIVED_SHARD_NAME")
            index=int(match.group(1))
            if index not in ledger_indices or index in archived:
                return fail("ARCHIVED_SHARD_OUTSIDE_CHECKPOINT")
            archived[index]=path
        if not archived:return fail("NO_ARCHIVED_ORIGINAL_SHARDS")
        if not isinstance(reports,list) or len(reports)>1000:
            return fail("INVALID_OR_UNBOUNDED_RECEIPTS")
        proven={}
        replayed={}
        gap_reason_by_issuer={}
        for j,report in enumerate(reports):
            if (not isinstance(report,dict)
                or report.get("phase")!="P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY"
                or report.get("status")!="PAGED_REAL_ARCHIVE_RESEARCH_ONLY"
                or report.get("trade_gate")!="BLOCKED"
                or report.get("orders")!=[]
                or report.get("executable_candidates")!=[]
                or report.get("actionable_buy_signals")!=[]
                or report.get("historical_PIT_verified") is not False
                or report.get("full_market_universe_verified") is not False
                or report.get("source_epoch_sha256")!=ledger["source_sha256"]
                or report.get("asof_completed_day")!=END
                or not isinstance(report.get("archive_commit_sha"),str)
                or not SHA40.fullmatch(report["archive_commit_sha"])):
                return fail(f"REPORT_{j}_UNSAFE_OR_WRONG_EPOCH")
            selected=report.get("selected_shards")
            features=report.get("features")
            gaps=report.get("evidence_gaps")
            if (not isinstance(selected,list) or not 1<=len(selected)<=16
                or len(set(selected))!=len(selected)
                or not isinstance(features,list) or not isinstance(gaps,list)
                or type(report.get("processed_shards")) is not int
                or report["processed_shards"]!=len(selected)):
                return fail(f"REPORT_{j}_INVALID_STRUCTURE")
            expected_codes={}
            for label in selected:
                match=SHARD.fullmatch(label) if isinstance(label,str) else None
                if not match or int(match.group(1)) not in archived:
                    return fail(f"REPORT_{j}_SHARD_NOT_ARCHIVED")
                index=int(match.group(1))
                if index not in replayed:
                    verified=assess(archived[index].parent)
                    if verified.get("trade_gate")!="BLOCKED":
                        return fail("UNSAFE_ORIGINAL_BAR_AUDIT")
                    original=json.loads(archived[index].read_text())
                    replayed[index]={
                        row["code"]:(row["sha256"],index)
                        for row in original["results"]}
                    if len(replayed[index])!=original["issuer_count"]:
                        return fail("ORIGINAL_SHARD_ISSUER_MISMATCH")
                for code,info in replayed[index].items():
                    if code in expected_codes:return fail("REPEATED_ISSUER_IN_REPORT")
                    expected_codes[code]=info
            seen={}
            for item in features:
                if not isinstance(item,dict) or not isinstance(item.get("issuer"),str):
                    return fail(f"REPORT_{j}_INVALID_FEATURE")
                code=item["issuer"]
                if code in seen or code not in expected_codes:
                    return fail(f"REPORT_{j}_UNKNOWN_OR_DUPLICATE_ISSUER")
                if (item.get("source_original_sha256")!=expected_codes[code][0]
                    or item.get("asof_completed_day")!=END
                    or item.get("buy_signal") is not False):
                    return fail(f"REPORT_{j}_FEATURE_PROVENANCE_MISMATCH")
                seen[code]="FEATURE"
            for item in gaps:
                if not isinstance(item,dict) or not isinstance(item.get("issuer"),str):
                    return fail(f"REPORT_{j}_INVALID_GAP")
                code=item["issuer"]
                if (code in seen or code not in expected_codes
                    or not isinstance(item.get("reason"),str)
                    or not item["reason"]):
                    return fail(f"REPORT_{j}_UNKNOWN_OR_DUPLICATE_GAP")
                previous_reason=gap_reason_by_issuer.get(code)
                if previous_reason is not None and previous_reason!=item["reason"]:
                    return fail("CONFLICTING_REPEAT_GAP_REASON")
                gap_reason_by_issuer[code]=item["reason"]
                seen[code]="GAP"
            if set(seen)!=set(expected_codes):
                return fail(f"REPORT_{j}_MISSING_ISSUER_EVIDENCE")
            if (type(report.get("scoped_verified_issuers")) is not int
                or report["scoped_verified_issuers"]!=len(expected_codes)
                or type(report.get("computed_feature_issuers")) is not int
                or report["computed_feature_issuers"]!=len(features)
                or type(report.get("missing_feature_evidence_issuers")) is not int
                or report["missing_feature_evidence_issuers"]!=len(gaps)):
                return fail(f"REPORT_{j}_COUNTS_MISMATCH")
            for label in selected:
                index=int(SHARD.fullmatch(label).group(1))
                codes=set(replayed[index])
                per_shard={code:seen[code] for code in codes}
                if index in proven and proven[index]!=per_shard:
                    return fail("CONFLICTING_REPEAT_SHARD_RECEIPT")
                proven[index]=per_shard
        observed=set(proven)
        fully_featured={i for i,items in proven.items() if all(x=="FEATURE" for x in items.values())}
        gap_shards=observed-fully_featured
        never_seen=set(archived)-observed
        feature_codes={code for items in proven.values() for code,state in items.items()
                       if state=="FEATURE"}
        missing_codes={code for items in proven.values() for code,state in items.items()
                       if state=="GAP"}
        if set(gap_reason_by_issuer)!=missing_codes:
            return fail("GAP_REASONS_NOT_RECONCILED")
        observed_issuers=len(feature_codes)+len(missing_codes)
        unobserved_issuers=ledger["completed_issuers"]-observed_issuers
        if unobserved_issuers<0:
            return fail("IMPOSSIBLE_OBSERVED_ISSUER_COUNT")
        gap_reason_counts={reason:sum(1 for r in gap_reason_by_issuer.values() if r==reason)
                           for reason in sorted(set(gap_reason_by_issuer.values()))}
        # Explicit research repair queue: frozen shard and issuer provenance,
        # never a trade or a synthetic "feature complete" label.
        gap_repair_queue=[
            {
                "shard_id":f"shard_{i:04d}",
                "issuer_gap_count":sum(state=="GAP" for state in proven[i].values()),
                "issuer_reasons":[
                    {"issuer":code,"reason":gap_reason_by_issuer[code]}
                    for code,state in sorted(proven[i].items()) if state=="GAP"
                ],
            }
            for i in sorted(gap_shards)
        ]
        if (len(gap_repair_queue)!=len(gap_shards)
            or sum(x["issuer_gap_count"] for x in gap_repair_queue)!=len(missing_codes)
            or {item["issuer"] for row in gap_repair_queue
                for item in row["issuer_reasons"]}!=missing_codes):
            return fail("GAP_REPAIR_QUEUE_NOT_RECONCILED")
        return dict(base,status="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
                    source_epoch_sha256=ledger["source_sha256"],
                    checkpoint_completed_shards=ledger["completed_shards"],
                    checkpoint_total_shards=ledger["shard_count"],
                    archived_original_shards=len(archived),
                    coverage_report_count=len(reports),
                    observed_archived_shards=len(observed),
                    feature_complete_shards=len(fully_featured),
                    observed_with_feature_gaps_shards=len(gap_shards),
                    unobserved_archived_shards=len(never_seen),
                    observed_shard_ids=[f"shard_{i:04d}" for i in sorted(observed)],
                    unobserved_shard_ids=[f"shard_{i:04d}" for i in sorted(never_seen)],
                    gap_shard_ids=[f"shard_{i:04d}" for i in sorted(gap_shards)],
                    feature_issuer_count=len(feature_codes),
                    issuer_evidence_gap_count=len(missing_codes),
                    observed_feature_or_gap_issuers=observed_issuers,
                    unobserved_issuer_count=unobserved_issuers,
                    gap_reason_counts=gap_reason_counts,
                    gap_issuer_codes=sorted(missing_codes),
                    gap_repair_queue=gap_repair_queue,
                    gap_repair_queue_is_research_only=True,
                    full_archive_evidence_accounted=(len(never_seen)==0 and
                                                    len(archived)==ledger["completed_shards"]),
                    full_archive_feature_coverage=(len(never_seen)==0 and
                                                   len(gap_shards)==0 and
                                                   len(archived)==ledger["completed_shards"]),
                    limitations=[
                        "CROSS_RUN_RECEIPTS_NOT_EXCHANGE_ATTESTED",
                        "ORIGINAL_VENDOR_CSV_NOT_HISTORICAL_PIT_CERTIFIED",
                        "FEATURE_COVERAGE_DOES_NOT_PROVE_FULL_MARKET_OR_STRATEGY",
                        "NO_LIVE_EXECUTION_OR_BROKER_FILLS",
                    ])
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return fail("COVERAGE_SOURCE_INTEGRITY_ERROR")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-epoch",required=True)
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--receipts",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        ledger=json.loads(Path(a.checkpoint).read_text())
        receipts=[json.loads(f.read_text()) for f in
                  sorted(Path(a.receipts).glob("*.json"))]
        r=summarize(a.archive_epoch,ledger,receipts)
    except (OSError,ValueError,UnicodeError):
        r=summarize(None,None,None)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:r.get(k) for k in (
        "status","reason","observed_archived_shards","feature_complete_shards",
        "unobserved_archived_shards","feature_issuer_count",
        "unobserved_issuer_count","gap_reason_counts",
        "full_archive_evidence_accounted","trade_gate")}))
    if r["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
