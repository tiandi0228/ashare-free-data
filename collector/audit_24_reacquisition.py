"""Audit three real capped cloud re-acquisitions against the 24 frozen SHA corpus.

Original market CSVs are neither preserved by this evidence nor
licensed for redistribution. Research data remain unverified exchange PIT.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(frozen, first16, last8):
    baseline=frozen.get("audit_report",{})
    require(
        frozen.get("evidence_type")=="PUBLIC_P1_LIMITED_24_ISSUER_CROSS_RUN_SOURCE_DIGEST_REPORT" and
        frozen.get("aggregation_run_id")==39590598008 and
        baseline.get("frozen_issuer_count")==24 and
        baseline.get("original_source_rows")==11563 and
        baseline.get("official_historical_point_in_time_issuer_pool_verified") is False and
        baseline.get("full_mainboard_historical_backfill_complete") is False and
        baseline.get("trade_gate")=="BLOCKED" and
        baseline.get("orders")==[],
        "Original frozen 24-source corpus is not eligible"
    )
    require(
        first16.get("capture_run_id")==39611226852 and
        first16.get("run_result")=="success" and
        first16.get("issuer_count")==16 and
        first16.get("source_queries_total")==16 and
        first16.get("source_rows_total")==7760 and
        first16.get("matching_sha_count")==16 and
        first16.get("original_raw_bytes_published") is False and
        first16.get("original_raw_bytes_permanently_archived") is False and
        first16.get("provider_market_data_redistribution_license_verified") is False and
        first16.get("trade_gate")=="BLOCKED" and
        first16.get("orders")==[],
        "Real two-batch source re-acquisition proof changed"
    )
    require(
        last8.get("source_run_id")==39610601436 and
        last8.get("observed_unique_issuers")==8 and
        last8.get("observed_rows_total")==3803 and
        last8.get("original_source_bytes_preserved") is False and
        last8.get("raw_vendor_CSV_redistribution_licensed") is False and
        last8.get("historical_PIT_verified") is False and
        last8.get("trade_gate")=="BLOCKED" and
        last8.get("orders")==[],
        "Real delisted-batch source re-acquisition proof changed"
    )
    batches=first16.get("verified_source_batches")
    tail=last8.get("original_comparison")
    require(isinstance(batches,list) and len(batches)==2 and isinstance(tail,dict),
            "Expected exactly three independent source batch reports")
    batches=batches+[tail]
    original=baseline.get("original_sha_receipts")
    require(isinstance(original,list) and len(original)==24,
            "Missing reference source SHA data")
    code_hash={p["code"]:p["sha256"] for p in original}
    require(len(code_hash)==24, "Duplicate frozen historical source identity")
    rows, seen = 0, set()
    for index, report in enumerate(batches):
        require(
            report.get("phase")=="P1_FROZEN_24_SOURCE_REACQUIRE_EIGHT_NO_RAW_REDISTRIBUTION" and
            report.get("status")=="EIGHT_SOURCE_BYTES_IDENTICAL_NOW_RESEARCH_ONLY" and
            report.get("batch_index")==index and
            report.get("batch_size")==8 and
            report.get("logical_issuer_queries")==8 and
            report.get("identical_source_count")==8 and
            report.get("provider_historical_versions_immutable") is False and
            report.get("original_raw_CSV_durably_archived") is False and
            report.get("provider_market_data_republication_license_verified") is False and
            report.get("official_exchange_historical_PIT_verified") is False and
            report.get("all_24_history_recovered_in_this_run") is False and
            report.get("trade_gate")=="BLOCKED" and
            report.get("orders")==[] and
            report.get("candidate_universe")==[] and
            report.get("executable_candidates")==[] and
            report.get("paid_api_calls")==0,
            "Batch source may not be elevated from temporary vendor evidence"
        )
        entries=report.get("source_entries")
        require(isinstance(entries,list) and len(entries)==8 and
                len(report.get("batch_source_codes",[]))==8,
                "Eight issuer source entries missing")
        require([p["code"] for p in entries]==report["batch_source_codes"] and
                [p["code"] for p in entries]==[p["code"] for p in original[index*8:(index+1)*8]],
                "Source batch order drift")
        for p in entries:
            code=p.get("code")
            require(code in code_hash and code not in seen,
                    "Unknown or repeated source issuer")
            seen.add(code)
            require(
                p.get("status")=="BYTE_IDENTICAL_AT_CURRENT_QUERY" and
                p.get("sha256_matches_frozen_original") is True and
                p.get("previous_source_sha256")==code_hash[code] and
                p.get("current_source_sha256")==code_hash[code] and
                type(p.get("previous_row_count")) is int and
                p.get("previous_row_count")==p.get("current_row_count") and
                p.get("underlying_source_original_bytes_copied_to_public_git") is False,
                "Vendor original source hash, count or public data policy mismatch"
            )
            rows+=p["current_row_count"]
    require(seen==set(code_hash) and rows==11563,
            "Not all 24 original source rows re-acquired identically")
    return {
        "phase":"P1_24_OF_24_REAL_ORIGINAL_SHA_REACQUISITION_AUDIT",
        "status":"24_FROZEN_RESEARCH_SOURCE_BYTES_IDENTICAL_AT_CAPTURE_TIME",
        "original_capture_runs":[39572697952,39573265839,39589103403],
        "reacquisition_runs":[39611226852,39610601436],
        "matching_issuers":24,
        "verified_reacquired_rows":rows,
        "number_of_independent_capped_batches":3,
        "all_24_original_bytes_rechecked_on_new_source_calls":True,
        "source_raw_originals_permanently_archived":False,
        "license_for_public_raw_market_CSV":False,
        "vendor_historical_revisions_impossible":False,
        "original_historical_publication_instant_authenticated":False,
        "complete_mainboard_PIT_verified":False,
        "p3_historical_official_ST_halt_delist_verified":False,
        "p4_actual_OOS_validated":False,
        "trade_gate":"BLOCKED",
        "orders":[],"candidate_universe":[],"executable_candidates":[],
        "paid_api_calls":0,
        "frozen_source_sha_receipts":original,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",default="reports/p1_research_24_coverage_20261021.json")
    ap.add_argument("--first16",default="reports/p1_reacquire_16_batches_01_20261021.json")
    ap.add_argument("--last8",default="reports/p1_reacquire_8_of_24_batch_2_20261021.json")
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    result=audit(read(args.baseline),read(args.first16),read(args.last8))
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
