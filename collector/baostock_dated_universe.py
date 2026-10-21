"""Two dated Baostock issuer snapshots — UNVERIFIED research, never PIT-certified.

Two query_all_stock calls at most, one login, no historical bar fetching,
no retry or fallback. Original response and mainboard-only subset are SHA-pinned.
A retrospective vendor snapshot is not an official timestamped historical pool.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

DATES = ("2025-05-26", "2026-10-20")
FIELDS = ("code", "tradeStatus", "code_name")
MAINBOARD = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
MAX_SOURCE_ROWS = 10000
MAX_CSV_BYTES = 2_000_000
MIN_MAINBOARD_ISSUERS = 1000
HALT_CASE = "sh.603019"
BLOCK = {
    "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    "paid_api_calls": 0, "exchange_publisher_authenticated": False,
    "retrospective_provider_snapshot": True,
    "point_in_time_issuer_membership_verified": False,
    "historical_st_delist_completeness_verified": False,
    "market_wide_historical_bars_complete": False,
    "backtest_or_live_recommendations_validated": False,
}


def csv_bytes(rows):
    dest = io.StringIO(newline="")
    writer = csv.writer(dest, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(rows)
    raw = dest.getvalue().encode("utf-8")
    if len(raw) > MAX_CSV_BYTES:
        raise ValueError("Source response exceeds frozen CSV byte limit")
    return raw


def inspect_rows(rows, minimum=MIN_MAINBOARD_ISSUERS):
    """Preserve returned order in originals; verify identities before filtering."""
    if len(rows) > MAX_SOURCE_ROWS:
        raise ValueError("Too many source rows")
    seen = set()
    main = []
    for row in rows:
        if len(row) != len(FIELDS):
            raise ValueError("Malformed source row")
        code, status, name = row
        if not isinstance(code, str) or code in seen or not code:
            raise ValueError("Missing or duplicate source code")
        seen.add(code)
        if MAINBOARD.fullmatch(code):
            if status not in ("0", "1") or not isinstance(name, str) or not name.strip():
                raise ValueError("Mainboard source trade status or name invalid")
            main.append(row)
    if len(main) < minimum:
        raise ValueError("Implausibly small mainboard subset")
    return main


def capture(out, provider, minimum=MIN_MAINBOARD_ISSUERS):
    path = Path(out)
    path.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "P1_FREE_BAOSTOCK_DATED_UNIVERSE_SNAPSHOT",
        "status": "BLOCKED_PARTIAL",
        "source": "Baostock query_all_stock(day)",
        "requested_dates": list(DATES),
        "login_attempts": 1,
        "logical_query_attempts": 0,
        "underlying_protocol_request_count_verified": False,
        "date_results": [],
        **BLOCK,
    }
    logged = False
    try:
        login = provider.login()
        if login.error_code != "0":
            report["login_error_code"] = str(login.error_code)[:24]
            raise ValueError("Provider login failed")
        logged = True
        for day in DATES:
            item = {"date": day, "status": "ERROR", "mainboard_prefix_only": True}
            report["logical_query_attempts"] += 1
            try:
                response = provider.query_all_stock(day=day)
                if response.error_code != "0" or tuple(response.fields) != FIELDS:
                    raise ValueError("Unexpected provider status or field schema")
                rows = []
                while response.next():
                    rows.append(response.get_row_data())
                    if len(rows) > MAX_SOURCE_ROWS:
                        raise ValueError("Exceeded maximum source rows")
                main = inspect_rows(rows, minimum)
                original = csv_bytes(rows)
                subset = csv_bytes(main)
                by_code = {row[0]: row for row in main}
                halt_status = by_code.get(HALT_CASE, [None, None])[1]
                # A known real issuer announcement says sh.603019 was halted
                # May 26 2025. A vendor discrepancy must fail closed.
                if day == "2025-05-26" and halt_status != "0":
                    raise ValueError("Historical known halt event not represented as suspended")
                original_name = f"all_securities_{day}.csv"
                filtered_name = f"mainboard_prefix_{day}.csv"
                (path / original_name).write_bytes(original)
                (path / filtered_name).write_bytes(subset)
                item.update({
                    "status": "OBSERVED_UNVERIFIED",
                    "source_all_security_rows": len(rows),
                    "mainboard_prefix_rows": len(main),
                    "mainboard_status_1": sum(r[1] == "1" for r in main),
                    "mainboard_status_0": sum(r[1] == "0" for r in main),
                    "known_halt_case_status": halt_status,
                    "original_csv_file": original_name,
                    "original_csv_sha256": hashlib.sha256(original).hexdigest(),
                    "mainboard_csv_file": filtered_name,
                    "mainboard_csv_sha256": hashlib.sha256(subset).hexdigest(),
                    "st_name_flags_observed_not_authoritative": sum(
                        r[2].upper().lstrip().startswith(("ST", "*ST")) for r in main
                    ),
                })
            except Exception as exc:
                item["error_type"] = type(exc).__name__
            report["date_results"].append(item)
        if (len(report["date_results"]) == len(DATES) and
                all(row["status"] == "OBSERVED_UNVERIFIED" for row in report["date_results"])):
            report["status"] = "OBSERVED_TWO_DATED_PROVIDER_SNAPSHOTS_UNVERIFIED"
    except Exception as exc:
        report["login_error_type"] = type(exc).__name__
    finally:
        if logged:
            try:
                provider.logout()
            except Exception:
                pass
        (path / "quality.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "OBSERVED_TWO_DATED_PROVIDER_SNAPSHOTS_UNVERIFIED" else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    import baostock
    raise SystemExit(capture(args.out, baostock))


if __name__ == "__main__":
    main()
