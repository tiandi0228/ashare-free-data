"""Replay a bounded REAL Baostock GitHub artifact without provider requests.

Original CSV bytes stay in an expiring Actions artifact. This checks source
SHA/date/trading-status semantics; it cannot certify exchange publication or
historical point-in-time membership, and never emits orders.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from collector.baostock_batch import CAP, END, FIELDS, START, manifest

ISSUER = "sh.600421"
LAST_STATUS_1 = "2026-06-22"
LAST_VENDOR_ROW = "2026-06-25"
REQUIRED_STATES = {
    "2026-05-26": "0", "2026-06-01": "1",
    "2026-06-22": "1", "2026-06-23": "0",
    "2026-06-24": "0", "2026-06-25": "0",
}
SOURCE_RUN = 39589103403
MAX_ORIGINAL_BYTES = 250000


def require(ok, why):
    if not ok:
        raise ValueError(why)


def verify_rows(code, raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ORIGINAL_BYTES,
            "Missing or oversized original issuer CSV bytes")
    try:
        r = csv.DictReader(io.StringIO(raw.decode("utf-8")))
        require(r.fieldnames == FIELDS, "Original source CSV schema mismatch")
        rows = list(r)
        require(1 <= len(rows) <= 600, "Original row count outside safety bound")
        require(all(None not in row and all(v is not None for v in row.values())
                    for row in rows), "Malformed source CSV row")
        dates = [row["date"] for row in rows]
        require(dates == sorted(set(dates)), "Date duplication or ordering mismatch")
        require(all(START <= d <= END and date.fromisoformat(d) for d in dates),
                "Source date out of frozen capture scope")
        require(all(row["code"] == code for row in rows), "Issuer identity mismatch")
        statuses = [row["tradestatus"] for row in rows]
        require(all(s in ("0", "1") for s in statuses),
                "Unexpected trading-status encoding")
        for row in rows:
            px = [Decimal(row[key]) for key in ("open", "high", "low", "close")]
            require(all(p.is_finite() and p > 0 for p in px) and
                    px[2] <= min(px[0], px[3]) <= max(px[0], px[3]) <= px[1],
                    "Invalid OHLC decimal or range")
    except (UnicodeDecodeError, csv.Error, InvalidOperation) as exc:
        raise ValueError("Unparseable original source CSV") from exc
    by_date = {row["date"]: row["tradestatus"] for row in rows}
    active_dates = [row["date"] for row in rows if row["tradestatus"] == "1"]
    require(active_dates, "No original row with trading-status 1")
    if code == ISSUER:
        for day, state in REQUIRED_STATES.items():
            require(by_date.get(day) == state,
                    "Known delisting-period source date/state case mismatch")
        require(active_dates[-1] == LAST_STATUS_1,
                "Delisted original last active-status day inconsistent")
        require(dates[-1] == LAST_VENDOR_ROW,
                "Delisted original last source date inconsistent")
    return {
        "code": code, "source_rows": len(rows),
        "trade_status_1_rows": len(active_dates),
        "trade_status_0_rows": len(rows) - len(active_dates),
        "last_status_1_date": active_dates[-1],
        "last_original_csv_date": dates[-1],
        "first_original_csv_date": dates[0],
        "original_csv_sha256": hashlib.sha256(raw).hexdigest(),
    }


def audit_zip(zipfile_path, manifest_path):
    symbols, manifest_sha = manifest(manifest_path)
    require(len(symbols) == CAP and symbols[0] == ISSUER,
            "Frozen eight-issuer historical pilot manifest changed")
    with ZipFile(zipfile_path) as z:
        require(set(z.namelist()) == {"quality.json"} | {
            code.replace(".", "_") + ".csv" for code in symbols
        }, "Missing, extra, or renamed artifact members")
        quality_raw = z.read("quality.json")
        require(len(quality_raw) <= 25000, "Source receipt too large")
        quality = json.loads(quality_raw)
        require(quality.get("phase") == "BAOSTOCK_FREE_BOUNDED_BATCH" and
                quality.get("status") == "OBSERVED_SUBSET_UNVERIFIED" and
                quality.get("batch_index") == 0 and
                quality.get("batch_count") == 1 and
                quality.get("issuer_count") == CAP and
                quality.get("query_attempts") == CAP and
                quality.get("login_attempts") == 1 and
                quality.get("manifest_sha256") == manifest_sha,
                "Quality receipt not eligible for frozen pilot")
        require(quality.get("paid_api_calls") == 0 and
                quality.get("trade_gate") == "BLOCKED" and
                quality.get("orders") == [] and quality.get("executable_candidates") == [] and
                quality.get("historical_point_in_time_universe_verified") is False and
                quality.get("historical_ST_halt_delist_verified") is False and
                quality.get("full_market_history_verified") is False,
                "Source receipt falsely elevated to trade or historical PIT")
        receipts = quality.get("results")
        require(isinstance(receipts, list) and
                [item.get("code") for item in receipts] == symbols,
                "Issuer order or receipt count incorrect")
        outcomes = []
        for item in receipts:
            code = item["code"]
            require(item.get("status") == "OBSERVED_UNVERIFIED",
                    "Incomplete issuer source data")
            raw = z.read(code.replace(".", "_") + ".csv")
            details = verify_rows(code, raw)
            require(item.get("sha256") == details["original_csv_sha256"] and
                    item.get("rows") == details["source_rows"] and
                    item.get("tradable_rows") == details["trade_status_1_rows"] and
                    item.get("suspended_status_rows") == details["trade_status_0_rows"] and
                    item.get("first") == details["first_original_csv_date"] and
                    item.get("last") == details["last_original_csv_date"],
                    "Source receipt differs from actual original CSV bytes")
            outcomes.append(details)
    require(outcomes[0]["source_rows"] == 408 and
            outcomes[0]["trade_status_0_rows"] == 30 and
            all(x["source_rows"] == 485 and x["trade_status_0_rows"] == 0
                for x in outcomes[1:]),
            "One-off original research pilot source coverage changed")
    return {
        "phase": "P1_EIGHT_ISSUER_DELISTED_ORIGINAL_BYTE_AUDIT",
        "status": "ORIGINAL_SOURCE_BYTES_REPLAYED_RESEARCH_ONLY",
        "frozen_capture_run_id": SOURCE_RUN,
        "original_csv_issuer_count": len(outcomes),
        "original_csv_total_rows": sum(x["source_rows"] for x in outcomes),
        "trade_status_1_total_rows": sum(x["trade_status_1_rows"] for x in outcomes),
        "trade_status_0_total_rows": sum(x["trade_status_0_rows"] for x in outcomes),
        "delisted_issuer_last_status_1_date": outcomes[0]["last_status_1_date"],
        "delisted_issuer_last_vendor_row_date": outcomes[0]["last_original_csv_date"],
        "independent_actual_exchange_pit_verified": False,
        "one_issuer_event_not_market_wide": True,
        "data_retention_depends_on_actions_artifact": True,
        "source_observed_during_later_replay_not_historical_asof": True,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "paid_api_calls": 0, "source_receipts": outcomes,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artifact", required=True)
    p.add_argument("--manifest", default="manifests/baostock_delisted_8_pilot.txt")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = audit_zip(args.artifact, args.manifest)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
