"""At-most-two real Baostock daily historical vendor ST+halt probes.

Vendor isST and tradestatus are *not* authenticated SSE/SZSE or historical
publication-time guarantees. Raw source CSV goes to a temporary Artifact.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path

CODES = ("sh.600421", "sh.603019")
FIELDS = ("date", "code", "tradestatus", "isST")
FIRST = "2025-05-20"
LAST = "2026-06-25"
MAX_ROWS = 350
MAX_BYTES = 50000


def require(ok, why):
    if not ok:
        raise ValueError(why)


def validate(code, rows):
    require(code in CODES and 1 <= len(rows) <= MAX_ROWS,
            "Unknown issuer or excessive rows")
    dates, seen = [], set()
    for row in rows:
        require(isinstance(row, (list, tuple)) and len(row) == 4 and
                all(isinstance(x, str) for x in row), "Malformed source row")
        day, issuer, status, risk = row
        require(issuer == code and FIRST <= day <= LAST, "Code/date scope error")
        date.fromisoformat(day)
        require(day not in seen and (not dates or day > dates[-1]),
                "Repeated or unordered source date")
        require(status in ("0", "1"), "Vendor trading status unknown")
        # Empty ST status is allowed *only* on a suspended placeholder.
        # It is never silently treated as isST=0.
        require(risk in ("0", "1") or (status == "0" and risk == ""),
                "Unverifiable vendor ST state on active day")
        seen.add(day)
        dates.append(day)
    by_day = {row[0]: row for row in rows}
    if code == "sh.603019":
        require(by_day.get("2025-05-26", [None, None, None])[2] == "0",
                "Known 603019 suspended-status event absent")
    if code == "sh.600421":
        for day, expected in (("2026-06-22", "1"),
                              ("2026-06-23", "0"),
                              ("2026-06-24", "0"),
                              ("2026-06-25", "0")):
            require(by_day.get(day, [None, None, None])[2] == expected,
                    "Known 600421 final trading/suspended statuses differ")
    count1 = sum(r[3] == "1" for r in rows)
    count0 = sum(r[3] == "0" for r in rows)
    unknown = len(rows) - count1 - count0
    require(count1 + count0 >= 20,
            "Insufficient explicit historical vendor ST observations")
    sink = io.StringIO(newline="")
    writer = csv.writer(sink, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(rows)
    raw = sink.getvalue().encode("utf-8")
    require(0 < len(raw) <= MAX_BYTES, "Source evidence too large")
    return raw, {
        "code": code,
        "first_date": dates[0], "last_date": dates[-1],
        "rows": len(rows),
        "vendor_ST_1_rows": count1, "vendor_ST_0_rows": count0,
        "vendor_ST_unknown_rows": unknown,
        "vendor_halted_rows": sum(r[2] == "0" for r in rows),
        "original_csv_sha256": hashlib.sha256(raw).hexdigest(),
        "original_csv_bytes": len(raw),
        "is_exchange_signed_historical_ST": False,
        "is_original_historical_publication_time": False,
    }


def capture(out, provider):
    path = Path(out)
    path.mkdir(parents=True, exist_ok=True)
    q = {
        "phase": "P3_BAOSTOCK_TWO_ISSUER_HISTORICAL_VENDOR_ST",
        "status": "BLOCKED_PARTIAL",
        "provider": "Baostock query_history_k_data_plus",
        "fields": list(FIELDS),
        "range": [FIRST, LAST],
        "login_attempts": 1, "logical_issuer_queries": 0,
        "max_source_queries": 2,
        "underlying_provider_network_calls_verified": False,
        "issuer_results": [],
        "source_exchange_authenticated": False,
        "historical_asof_publication_authenticated": False,
        "full_market_ST_halt_delist_complete": False,
        "vendor_isST_equivalent_to_official_notice": False,
        "data_redistribution_license_verified": False,
        "paid_api_calls": 0,
        "trade_gate": "BLOCKED",
        "candidate_universe": [],
        "orders": [], "executable_candidates": [],
    }
    logged = False
    try:
        s = provider.login()
        require(s.error_code == "0", "Baostock login failed")
        logged = True
        for code in CODES:
            info = {"code": code, "status": "ERROR"}
            q["logical_issuer_queries"] += 1
            try:
                s = provider.query_history_k_data_plus(
                    code,
                    fields=",".join(FIELDS),
                    start_date=FIRST, end_date=LAST,
                    frequency="d", adjustflag="3",
                )
                require(s.error_code == "0" and tuple(s.fields) == FIELDS,
                        "Provider ST fields not returned")
                rows = []
                while s.next():
                    rows.append(s.get_row_data())
                    require(len(rows) <= MAX_ROWS, "Source row cap exceeded")
                raw, measured = validate(code, rows)
                (path / (code.replace(".", "_") + "_vendor_ST.csv")).write_bytes(raw)
                info.update(measured)
                info["status"] = "OBSERVED_VENDOR_ST_UNVERIFIED"
            except Exception as exc:
                info["failure_type"] = type(exc).__name__
            q["issuer_results"].append(info)
        if len(q["issuer_results"]) == 2 and all(
            r["status"] == "OBSERVED_VENDOR_ST_UNVERIFIED"
            for r in q["issuer_results"]
        ):
            q["status"] = "TWO_ISSUER_VENDOR_ST_OBSERVED_NOT_OFFICIAL"
    except Exception as exc:
        q["login_error_type"] = type(exc).__name__
    finally:
        if logged:
            try:
                provider.logout()
            except Exception:
                q["logout_failed"] = True
        (path / "quality.json").write_text(
            json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(q, ensure_ascii=False))
    return 0 if q["status"] == "TWO_ISSUER_VENDOR_ST_OBSERVED_NOT_OFFICIAL" else 2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args()
    import baostock as bs
    raise SystemExit(capture(args.out, bs))


if __name__ == "__main__":
    main()
