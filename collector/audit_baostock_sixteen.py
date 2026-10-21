"""Offline cross-run audit for two pinned Baostock eight-issuer evidence artifacts.

NO network market-data calls; this consumes already captured original CSV bytes.
A complete research pilot is not a historical point-in-time official security pool.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path

from collector.baostock_batch import CAP, END, FIELDS, START, manifest

EXPECTED_ISSUERS = 16
EXPECTED_ROWS_EACH = 485
EXPECTED_603019_HALTS = (
    "2025-05-26", "2025-05-27", "2025-05-28", "2025-05-29",
    "2025-05-30", "2025-06-03", "2025-06-04", "2025-06-05",
    "2025-06-06", "2025-06-09",
)

def validate(manifest_path, first_dir, second_dir, first_run, second_run):
    codes, manifest_sha = manifest(manifest_path)
    if len(codes) != EXPECTED_ISSUERS:
        raise ValueError("Expected exactly 16 frozen research pilot symbols")
    roots = (Path(first_dir), Path(second_dir))
    run_ids = (int(first_run), int(second_run))
    if len(set(run_ids)) != 2 or any(r <= 0 for r in run_ids):
        raise ValueError("Original run identities must be distinct")
    summaries = []
    all_calendar_sets = []
    for idx, root in enumerate(roots):
        quality = json.loads((root / "quality.json").read_text(encoding="utf-8"))
        selected = codes[idx * CAP:(idx+1) * CAP]
        if (
            quality.get("phase") != "BAOSTOCK_FREE_BOUNDED_BATCH"
            or quality.get("status") != "OBSERVED_SUBSET_UNVERIFIED"
            or quality.get("batch_index") != idx
            or quality.get("batch_count") != 2
            or quality.get("manifest_sha256") != manifest_sha
            or quality.get("issuer_count") != CAP
            or quality.get("query_attempts") != CAP
            or quality.get("login_attempts") != 1
            or quality.get("paid_api_calls") != 0
            or quality.get("trade_gate") != "BLOCKED"
            or quality.get("orders") != []
            or quality.get("executable_candidates") != []
            or quality.get("official_exchange_authenticated") is not False
            or quality.get("historical_point_in_time_universe_verified") is not False
        ):
            raise ValueError("Source quality receipt is not eligible")
        observations = quality.get("results")
        if not isinstance(observations, list) or [r.get("code") for r in observations] != selected:
            raise ValueError("Wrong or missing original issuer order")
        for observation in observations:
            code = observation["code"]
            if observation.get("status") != "OBSERVED_UNVERIFIED":
                raise ValueError("Invalid source issuer receipt")
            csv_path = root / (code.replace(".", "_") + ".csv")
            raw = csv_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != observation.get("sha256"):
                raise ValueError("Original source CSV SHA-256 mismatch: " + code)
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
            if reader.fieldnames != FIELDS:
                raise ValueError("Original CSV field layout mismatch")
            rows = list(reader)
            if len(rows) != observation.get("rows") or len(rows) != EXPECTED_ROWS_EACH:
                raise ValueError("Frozen pilot source row count changed")
            dates = [row["date"] for row in rows]
            if dates != sorted(set(dates)) or not all(START <= s <= END for s in dates):
                raise ValueError("Original date scope invalid")
            if any(row["code"] != code for row in rows):
                raise ValueError("Issuer identity inconsistent")
            statuses = [row["tradestatus"] for row in rows]
            if any(s not in ("0", "1") for s in statuses):
                raise ValueError("Unexpected market trade-status values")
            halted = [row["date"] for row in rows if row["tradestatus"] == "0"]
            if observation.get("tradable_rows") != statuses.count("1") or observation.get("suspended_status_rows") != len(halted):
                raise ValueError("Status count mismatch")
            if code == "sh.603019":
                if tuple(halted) != EXPECTED_603019_HALTS:
                    raise ValueError("603019 halt dates differ from verified issuer-event case")
            elif halted:
                raise ValueError("Unexpected pilot suspended rows in other observed issuer: " + code)
            for row in rows:
                date.fromisoformat(row["date"])
            all_calendar_sets.append(set(dates))
            summaries.append({
                "code": code, "run_id": run_ids[idx],
                "source_sha256": observation["sha256"],
                "source_rows": len(rows), "tradable_status_rows": statuses.count("1"),
                "suspended_status_rows": len(halted),
                "first_date": dates[0], "last_date": dates[-1],
            })
    if len({row["code"] for row in summaries}) != EXPECTED_ISSUERS:
        raise ValueError("Duplicated issuer across independently captured shards")
    common = set.intersection(*all_calendar_sets)
    union = set.union(*all_calendar_sets)
    if len(common) != EXPECTED_ROWS_EACH or len(union) != EXPECTED_ROWS_EACH:
        raise ValueError("Research pilot provider-session calendar inconsistency")
    report = {
        "phase": "P1_FREE_BAOSTOCK_16_ISSUER_CROSS_RUN_AUDIT",
        "status": "OBSERVED_16_CURRENT_ISSUERS_RESEARCH_ONLY",
        "source_run_ids": list(run_ids),
        "manifest_sha256": manifest_sha,
        "issuer_count": len(summaries),
        "original_source_rows": sum(r["source_rows"] for r in summaries),
        "trade_status_1_rows": sum(r["tradable_status_rows"] for r in summaries),
        "trade_status_0_rows": sum(r["suspended_status_rows"] for r in summaries),
        "common_provider_session_dates": len(common),
        "union_provider_session_dates": len(union),
        "earliest": min(common), "latest": max(common),
        "source": "Baostock public service",
        "first_party_exchange_authentication": False,
        "historical_point_in_time_universe_verified": False,
        "historical_ST_halt_delist_complete": False,
        "market_wide_backfill_complete": False,
        "backtest_or_live_signal_validated": False,
        "paid_api_calls": 0,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "issuers": summaries,
    }
    return report

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="manifests/baostock_pilot.txt")
    p.add_argument("--first", required=True)
    p.add_argument("--second", required=True)
    p.add_argument("--first-run", type=int, required=True)
    p.add_argument("--second-run", type=int, required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    report = validate(a.manifest, a.first, a.second, a.first_run, a.second_run)
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))

if __name__ == "__main__":
    main()
