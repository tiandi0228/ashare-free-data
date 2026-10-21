"""Aggregate 16+8 validated research issuer SHA receipts, never a full-market claim.

The original CSVs were independently re-verified in their own cloud audit runs.
This step uses SHA metadata only and must not treat retrospective vendor
membership, record counts, or recorded source status as a tradable PIT pool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ISSUER_PATTERN=re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
SHA_PATTERN=re.compile(r"[0-9a-f]{64}\Z")


def ensure(ok, reason):
    if not ok:
        raise ValueError(reason)


def evaluate(original16, latest8):
    first=original16.get("audit_report",{})
    second=latest8.get("replay_report",{})
    ensure(original16.get("evidence_type")==
           "SOURCE_SHA_METADATA_ONLY_NO_CSV_REDISTRIBUTION" and
           original16.get("capture_run_ids")==[39572697952,39573265839] and
           first.get("source_run_ids")==[39572697952,39573265839] and
           first.get("status")=="OBSERVED_16_CURRENT_ISSUERS_RESEARCH_ONLY" and
           first.get("issuer_count")==16 and
           first.get("original_source_rows")==7760 and
           first.get("trade_status_1_rows")==7750 and
           first.get("trade_status_0_rows")==10 and
           first.get("market_wide_backfill_complete") is False and
           first.get("historical_point_in_time_universe_verified") is False and
           first.get("trade_gate")=="BLOCKED" and
           first.get("orders")==[] and first.get("executable_candidates")==[],
           "The original 16-issuer real-source receipt is incomplete or promoted")
    ensure(latest8.get("evidence_type")==
           "P1_PUBLIC_BAOSTOCK_EIGHT_ISSUER_SOURCE_SHA_RECEIPT_ONLY" and
           latest8.get("source_run_id")==39589103403 and
           latest8.get("replay_audit_run_id")==39589886891 and
           latest8.get("actual_replay_verified") is True and
           latest8.get("original_csv_bytes_committed_to_git") is False and
           latest8.get("original_csv_sha_receipts_alone_not_reconstructible") is True and
           latest8.get("trade_gate")=="BLOCKED" and
           latest8.get("orders")==[] and latest8.get("executable_candidates")==[],
           "The new eight-issuer original-byte audit identity is invalid")
    ensure(second.get("status")=="ORIGINAL_SOURCE_BYTES_REPLAYED_RESEARCH_ONLY" and
           second.get("frozen_capture_run_id")==39589103403 and
           second.get("original_csv_issuer_count")==8 and
           second.get("original_csv_total_rows")==3803 and
           second.get("trade_status_1_total_rows")==3773 and
           second.get("trade_status_0_total_rows")==30 and
           second.get("independent_actual_exchange_pit_verified") is False and
           second.get("trade_gate")=="BLOCKED" and
           second.get("orders")==[] and second.get("executable_candidates")==[],
           "New source replay report is incomplete or falsely official")
    a=first.get("issuers")
    b=second.get("source_receipts")
    ensure(isinstance(a,list) and len(a)==16 and isinstance(b,list) and len(b)==8,
           "Expected 16 plus 8 original source digests")
    normalized=[]
    for entry in a:
        normalized.append({
            "code":entry["code"],
            "rows":entry["source_rows"],
            "status_1":entry["tradable_status_rows"],
            "status_0":entry["suspended_status_rows"],
            "sha256":entry["source_sha256"],
            "first":entry["first_date"],
            "last_source":entry["last_date"],
        })
    for entry in b:
        normalized.append({
            "code":entry["code"],
            "rows":entry["source_rows"],
            "status_1":entry["trade_status_1_rows"],
            "status_0":entry["trade_status_0_rows"],
            "sha256":entry["original_csv_sha256"],
            "first":entry["first_original_csv_date"],
            "last_source":entry["last_original_csv_date"],
        })
    codes=[x["code"] for x in normalized]
    ensure(len(set(codes))==24 and
           all(ISSUER_PATTERN.fullmatch(c) for c in codes),
           "Code duplication or out-of-scope issuer pool")
    ensure(all(SHA_PATTERN.fullmatch(x["sha256"]) and
               type(x["rows"]) is int and type(x["status_1"]) is int and
               type(x["status_0"]) is int and
               0 <= x["status_1"] <= x["rows"] <= 600 and
               x["status_0"]==x["rows"]-x["status_1"] and
               "2024-10-20" <= x["first"] <= x["last_source"] <= "2026-10-20"
               for x in normalized),
           "Original-source receipt row and SHA mismatch")
    ensure(sum(x["rows"] for x in normalized)==11563 and
           sum(x["status_1"] for x in normalized)==11523 and
           sum(x["status_0"] for x in normalized)==40,
           "Combined audit source accounting invalid")
    delisted=[x for x in b if x["code"]=="sh.600421"]
    ensure(len(delisted)==1 and delisted[0]["last_status_1_date"]=="2026-06-22" and
           delisted[0]["last_original_csv_date"]=="2026-06-25" and
           delisted[0]["source_rows"]==408 and
           delisted[0]["trade_status_0_rows"]==30,
           "Delisted issuer real-source temporal case not reproduced")
    return {
        "phase":"P1_FREE_RESEARCH_24_ISSUER_CROSS_RUN_COVERAGE",
        "status":"24_UNIQUE_SOURCE_ISSUERS_RESEARCH_ONLY",
        "source_captures":[39572697952,39573265839,39589103403],
        "independent_original_byte_audits":[39573806984,39589886891],
        "frozen_issuer_count":24,
        "original_source_rows":11563,
        "trade_status_1_rows":11523,
        "trade_status_0_rows":40,
        "delisted_600421_last_status_1_date":"2026-06-22",
        "delisted_600421_last_vendor_row_date":"2026-06-25",
        "all_original_bytes_rechecked_in_this_metadata_only_run":False,
        "original_csv_replay_dependence_on_expiring_artifacts":True,
        "official_historical_point_in_time_issuer_pool_verified":False,
        "full_mainboard_historical_backfill_complete":False,
        "ST_halt_delist_history_complete":False,
        "p4_out_of_sample_validated":False,
        "trade_gate":"BLOCKED","candidate_universe":[],
        "orders":[],"executable_candidates":[],"paid_api_calls":0,
        "original_sha_receipts":[{"code":x["code"],"sha256":x["sha256"]} for x in normalized],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--old",default="reports/p1_pilot_16_source_digests_20261021.json")
    ap.add_argument("--new",default="reports/p1_delisted_8_source_digests_20261021.json")
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    o=json.loads(Path(args.old).read_text(encoding="utf-8"))
    n=json.loads(Path(args.new).read_text(encoding="utf-8"))
    q=evaluate(o,n)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(q,ensure_ascii=False))


if __name__=="__main__":
    main()
