"""Independently replay two dated Baostock roster *original CSV byte streams*.

Research-only. Baostock query_all_stock(day) retrospectively returns a vendor
roster; a date argument or SHA match does NOT authenticate historical as-of
publication, official mainboard identity, ST, delisting, or a full-market PIT.
No market queries; no original CSV files are republished in this repository.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from collector.baostock_dated_universe import (
    DATES, FIELDS, MAINBOARD, MAX_SOURCE_ROWS, csv_bytes, inspect_rows,
)

CAPTURE_RUN = 39613467121
FROZEN = {
    "2025-05-26": {
        "all_rows": 6825, "main_rows": 3181, "active": 3163,
        "halted": 18, "st_name_count": 149,
        "all_sha": "3489ff2062502ec9ef0580ed9d2f94f93e250930f7adbe0765a0a169040f7da5",
        "main_sha": "b5abfe659520531dc81f07a8af0fea324c63091b6439540faed3bf023e2b80b6",
        "halt_603019": "0",
    },
    "2026-10-20": {
        "all_rows": 7440, "main_rows": 3195, "active": 3191,
        "halted": 4, "st_name_count": 143,
        "all_sha": "9c7f9fa7e8ad4a91bc6b5f54cbec26bbae9c2f2f8b79b8164653bfbcdf4b1696",
        "main_sha": "930a53f525471a92561457ec819c797f36292fc34a2b69df6889daa6a0178cc1",
        "halt_603019": "1",
    },
}
MAX_ZIP_BYTES = 2_500_000


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def parse_source(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 2_000_000,
            "Original source CSV missing or too large")
    try:
        table = csv.reader(io.StringIO(raw.decode("utf-8")))
        require(tuple(next(table, ())) == FIELDS, "Vendor CSV schema altered")
        rows = list(table)
        require(len(rows) <= MAX_SOURCE_ROWS, "Source row count exceeded")
        require(all(len(x) == len(FIELDS) for x in rows),
                "Original source CSV malformed")
        require(csv_bytes(rows) == raw,
                "Original raw-byte format differs from frozen producer")
        main = inspect_rows(rows, minimum=1000)
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise ValueError("Original CSV decoding/format failed") from exc
    return rows, main


def validate_day(day, original, filtered, receipt, frozen=FROZEN):
    require(day in frozen, "Unfrozen historical decision day")
    expected = frozen[day]
    require(isinstance(receipt, dict) and
            receipt.get("date") == day and
            receipt.get("status") == "OBSERVED_UNVERIFIED" and
            receipt.get("mainboard_prefix_only") is True,
            "Vendor day source receipt not auditable")
    require(hashlib.sha256(original).hexdigest() == expected["all_sha"] and
            hashlib.sha256(filtered).hexdigest() == expected["main_sha"],
            "Original SHA-256 differs from frozen source version")
    require(receipt.get("original_csv_sha256") == expected["all_sha"] and
            receipt.get("mainboard_csv_sha256") == expected["main_sha"],
            "Source receipt SHA-256 changed")
    rows, main = parse_source(original)
    require(csv_bytes(main) == filtered,
            "Filtered mainboard CSV differs from original vendor rows")
    require(len(rows) == expected["all_rows"] and
            len(main) == expected["main_rows"] and
            receipt.get("source_all_security_rows") == len(rows) and
            receipt.get("mainboard_prefix_rows") == len(main),
            "Vendor roster row-count drift")
    active = sum(r[1] == "1" for r in main)
    halted = sum(r[1] == "0" for r in main)
    st = sum(r[2].upper().lstrip().startswith(("ST", "*ST")) for r in main)
    require((active, halted, st) ==
            (expected["active"], expected["halted"], expected["st_name_count"]),
            "Source active/suspended/ST-name count drift")
    require(receipt.get("mainboard_status_1") == active and
            receipt.get("mainboard_status_0") == halted and
            receipt.get("st_name_flags_observed_not_authoritative") == st,
            "Quality receipt statistics differ from original rows")
    bycode={r[0]:r for r in main}
    require("sh.603019" in bycode and
            bycode["sh.603019"][1] == expected["halt_603019"] and
            receipt.get("known_halt_case_status") == expected["halt_603019"],
            "Historical known halt case not independently supported")
    require(all(MAINBOARD.fullmatch(r[0]) for r in main),
            "Non-mainboard code admitted to frozen provisional prefix subset")
    return {
        "decision_date": day,
        "source_original_rows":len(rows), "mainboard_prefix_rows":len(main),
        "mainboard_vendor_status_1":active,
        "mainboard_vendor_status_0":halted,
        "mainboard_st_name_flags":st,
        "known_603019_vendor_status":bycode["sh.603019"][1],
        "full_original_sha256":expected["all_sha"],
        "mainboard_subset_sha256":expected["main_sha"],
        "original_csv_reverified_in_this_audit":True,
        "exchange_official_asof_verified":False,
    }


def audit_archive(artifact):
    path=Path(artifact)
    require(path.is_file() and 0 < path.stat().st_size <= MAX_ZIP_BYTES,
            "Original dated-roster source artifact unavailable or too large")
    with ZipFile(path) as z:
        required={"quality.json"} | {
            name for day in DATES for name in (
                f"all_securities_{day}.csv", f"mainboard_prefix_{day}.csv"
            )
        }
        require(set(z.namelist()) == required,
                "Unexpected/missing original dated source files")
        require(all(0 < meta.file_size <= 2_000_000 for meta in z.infolist()),
                "Original source ZIP member exceeds bounded size")
        q=json.loads(z.read("quality.json"))
        require(q.get("phase") == "P1_FREE_BAOSTOCK_DATED_UNIVERSE_SNAPSHOT" and
                q.get("status") == "OBSERVED_TWO_DATED_PROVIDER_SNAPSHOTS_UNVERIFIED" and
                q.get("requested_dates") == list(DATES) and
                q.get("login_attempts") == 1 and
                q.get("logical_query_attempts") == 2 and
                q.get("source") == "Baostock query_all_stock(day)" and
                q.get("trade_gate") == "BLOCKED" and
                q.get("orders") == [] and q.get("executable_candidates") == [] and
                q.get("paid_api_calls") == 0 and
                q.get("exchange_publisher_authenticated") is False and
                q.get("retrospective_provider_snapshot") is True and
                q.get("point_in_time_issuer_membership_verified") is False and
                q.get("historical_st_delist_completeness_verified") is False and
                q.get("market_wide_historical_bars_complete") is False,
                "Dated vendor snapshot receipt falsely promoted to PIT")
        receipts=q.get("date_results")
        require(isinstance(receipts,list) and len(receipts)==2 and
                [r.get("date") for r in receipts]==list(DATES),
                "Frozen source dates missing or reordered")
        results=[]
        for day, receipt in zip(DATES, receipts):
            require(receipt.get("original_csv_file") == f"all_securities_{day}.csv" and
                    receipt.get("mainboard_csv_file") == f"mainboard_prefix_{day}.csv",
                    "Unexpected source filename in vendor quality receipt")
            results.append(validate_day(
                day, z.read(receipt["original_csv_file"]),
                z.read(receipt["mainboard_csv_file"]), receipt))
    return {
        "phase":"P1_TWO_DATED_VENDOR_ROSTER_ORIGINAL_BYTES_REPLAY",
        "status":"ORIGINAL_TWO_VENDOR_ROSTERS_REPLAYED_PIT_BLOCKED",
        "original_vendor_capture_run":CAPTURE_RUN,
        "historical_dates":list(DATES),
        "dated_originals_replayed_in_this_run":True,
        "issuer_pool_size_2025_05_26":results[0]["mainboard_prefix_rows"],
        "issuer_pool_size_2026_10_20":results[1]["mainboard_prefix_rows"],
        "provisional_prefix_pool_only":True,
        "retrospective_provider_revision_possible":True,
        "authenticated_as_of_publication_instant":False,
        "official_exchange_mainboard_membership_verified":False,
        "full_history_ST_halt_delist_verified":False,
        "full_market_two_year_bars_verified":False,
        "original_source_bytes_archived_permanently":False,
        "provider_data_republication_license_verified":False,
        "trade_gate":"BLOCKED",
        "candidate_universe":[],"orders":[],"executable_candidates":[],
        "paid_api_calls":0,
        "date_results":results,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifact", required=True)
    p.add_argument("--out", required=True)
    args=p.parse_args()
    report=audit_archive(args.artifact)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
