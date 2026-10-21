"""Reacquire 8/24 frozen free historical source CSVs by SHA, never re-publish.

An on-demand byte-identical observation is a CONDITIONAL research replay,
not historic original-byte custody, licensing, exchange PIT or trade approval.
No new universe is generated; each batch is exactly one of three frozen groups.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from collector.baostock_batch import CAP, END, FIELDS, START, manifest
from collector.audit_delisted_archive import verify_rows
from collector.research_24_coverage_gate import evaluate as verify_prior_sources

ALLOWED_BATCHES=(0,1,2)
EXPECTED_CAPTURE_RUNS=(39572697952,39573265839,39589103403)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def source_index(old, new, first_manifest, second_manifest):
    """Provenance check is offline and validates every required SHA/issuer scope."""
    certified=verify_prior_sources(old,new)
    require(certified["source_captures"]==list(EXPECTED_CAPTURE_RUNS),
            "Frozen source run evidence missing")
    a,sha_a=manifest(first_manifest)
    b,sha_b=manifest(second_manifest)
    codes=a+b
    require(len(a)==16 and len(b)==8 and len(codes)==24 and
            len(set(codes))==24,
            "24-source manifest drift")
    receipts=certified["original_sha_receipts"]
    require([r["code"] for r in receipts]==codes,
            "SHA provenance order differs from manifests")
    source_rows={
        item["code"]:item["source_rows"]
        for item in old["audit_report"]["issuers"]
    }
    source_rows.update({
        item["code"]:item["source_rows"]
        for item in new["replay_report"]["source_receipts"]
    })
    require(set(source_rows)==set(codes), "Original source row receipts incomplete")
    return {
        r["code"]:{
            "sha256":r["sha256"],
            "rows":source_rows[r["code"]],
            "manifest_sha256":sha_a if r["code"] in a else sha_b,
        } for r in receipts
    }, codes


def compare_source(code, rows, expected_sha, expected_count):
    """SHA equality includes every original row and its exact source ordering."""
    require(isinstance(rows, list) and 0 < len(rows) <= 600,
            "Empty or over-budget source history")
    require(all(isinstance(row,(list,tuple)) and
                len(row)==len(FIELDS) and
                all(isinstance(x,str) and "\n" not in x and "," not in x
                    for x in row)
                for row in rows),
            "Malformed source data cannot be serialized as original CSV")
    raw=(",".join(FIELDS)+"\n"+
         "".join(",".join(row)+"\n" for row in rows)).encode("utf-8")
    measured=verify_rows(code,raw)
    same=(measured["original_csv_sha256"]==expected_sha and
          measured["source_rows"]==expected_count)
    return {
        "code":code,
        "status":"BYTE_IDENTICAL_AT_CURRENT_QUERY" if same
                 else "SOURCE_HISTORY_REVISION_OR_SCHEMA_DRIFT",
        "sha256_matches_frozen_original":same,
        "previous_source_sha256":expected_sha,
        "current_source_sha256":measured["original_csv_sha256"],
        "previous_row_count":expected_count,
        "current_row_count":measured["source_rows"],
        "current_last_vendor_row":measured["last_original_csv_date"],
        "current_last_trade_status_1":measured["last_status_1_date"],
        "underlying_source_original_bytes_copied_to_public_git":False,
    }


def run(provider, index, baseline, codes):
    require(type(index) is int and index in ALLOWED_BATCHES and
            len(codes)==24 and set(codes)==set(baseline) and
            all(code in baseline for code in codes),
            "Unexpected historical batch universe")
    selected=codes[index*CAP:(index+1)*CAP]
    require(len(selected)==CAP and len(set(selected))==CAP,
            "Cap of eight unique symbols per provider session required")
    report={
        "phase":"P1_FROZEN_24_SOURCE_REACQUIRE_EIGHT_NO_RAW_REDISTRIBUTION",
        "status":"BLOCKED_INCOMPLETE_OR_REVISED",
        "batch_index":index,
        "batch_size":CAP,
        "batch_source_codes":selected,
        "original_source_capture_runs":list(EXPECTED_CAPTURE_RUNS),
        "query_start":START,"query_end":END,
        "query_fields":list(FIELDS),
        "adjustflag":"3","frequency":"d",
        "provider_login_attempts":1,
        "logical_issuer_queries":0,
        "logical_query_limit":CAP,
        "source_entries":[],
        "identical_source_count":0,
        "provider_historical_versions_immutable":False,
        "original_raw_CSV_durably_archived":False,
        "provider_market_data_republication_license_verified":False,
        "all_24_history_recovered_in_this_run":False,
        "official_exchange_historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],"candidate_universe":[],"executable_candidates":[],
        "paid_api_calls":0,
    }
    logged=False
    try:
        response=provider.login()
        require(getattr(response,"error_code",None)=="0",
                "Provider login failed")
        logged=True
        for code in selected:
            result={"code":code,"status":"SOURCE_UNAVAILABLE"}
            report["logical_issuer_queries"]+=1
            try:
                response=provider.query_history_k_data_plus(
                    code,fields=",".join(FIELDS),
                    start_date=START,end_date=END,frequency="d",adjustflag="3")
                require(getattr(response,"error_code",None)=="0" and
                        list(response.fields)==FIELDS,
                        "Provider historical fields unavailable")
                rows=[]
                while response.next():
                    require(len(rows)<600, "History row bound exceeded")
                    rows.append(response.get_row_data())
                frozen=baseline[code]
                result=compare_source(code,rows,frozen["sha256"],frozen["rows"])
                result["manifest_sha256"]=frozen["manifest_sha256"]
            except Exception as exc:
                result["failure_type"]=type(exc).__name__
            report["source_entries"].append(result)
    except Exception as exc:
        report["login_failure_type"]=type(exc).__name__
    finally:
        if logged:
            try:provider.logout()
            except Exception:report["logout_failed"]=True
    report["identical_source_count"]=sum(
        e.get("sha256_matches_frozen_original") is True
        for e in report["source_entries"])
    if report["identical_source_count"]==CAP:
        report["status"]="EIGHT_SOURCE_BYTES_IDENTICAL_NOW_RESEARCH_ONLY"
    report["observed_at_utc"]=datetime.now(timezone.utc).isoformat()
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--batch-index",type=int,choices=ALLOWED_BATCHES,required=True)
    p.add_argument("--pilot16",default="manifests/baostock_pilot.txt")
    p.add_argument("--pilot8",default="manifests/baostock_delisted_8_pilot.txt")
    p.add_argument("--old",default="reports/p1_pilot_16_source_digests_20261021.json")
    p.add_argument("--new",default="reports/p1_delisted_8_source_digests_20261021.json")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    def load(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    baseline,codes=source_index(load(args.old),load(args.new),
                                args.pilot16,args.pilot8)
    import baostock as bs
    report=run(bs,args.batch_index,baseline,codes)
    destination=Path(args.out)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    raise SystemExit(
        0 if report["status"]=="EIGHT_SOURCE_BYTES_IDENTICAL_NOW_RESEARCH_ONLY"
        else 2
    )


if __name__=="__main__":
    main()
