"""One free Baostock listing-lifecycle snapshot for research, never official PIT."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

DATES = ("2025-05-26", "2026-10-20")
FIELDS = ("code", "code_name", "ipoDate", "outDate", "type", "status")
MAINBOARD = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
MAX_ROWS = 12000
MAX_BYTES = 2500000
MIN_MAINBOARD = 1000

def source_csv(rows):
    sink = io.StringIO(newline="")
    writer = csv.writer(sink, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(rows)
    raw = sink.getvalue().encode("utf-8")
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Unexpected source CSV size")
    return raw

def parse_date(value, required):
    if not value or not value.strip():
        if required:
            raise ValueError("Missing IPO date")
        return None
    return date.fromisoformat(value)

def audit_rows(rows, min_mainboard=MIN_MAINBOARD):
    if len(rows) > MAX_ROWS:
        raise ValueError("Oversized source")
    seen, main = set(), []
    for row in rows:
        if len(row) != len(FIELDS) or not all(isinstance(s, str) for s in row):
            raise ValueError("Malformed issuer row")
        code, name, ipo, out, kind, status = row
        if not code or code in seen:
            raise ValueError("Missing or duplicate code")
        seen.add(code)
        if not MAINBOARD.fullmatch(code):
            continue
        if kind != "1" or status not in ("0", "1") or not name.strip():
            raise ValueError("Mainboard issuer type/status/name unverified")
        start, end = parse_date(ipo, True), parse_date(out, False)
        if end is not None and end < start:
            raise ValueError("Delisting precedes IPO")
        if status == "0" and end is None:
            raise ValueError("Delisted issuer has no dated boundary")
        main.append((code, name, start, end, status))
    if len(main) < min_mainboard:
        raise ValueError("Implausibly few mainboard issuer lifecycles")
    snapshots = []
    for stamp in DATES:
        today = date.fromisoformat(stamp)
        candidates = [x for x in main if x[2] <= today and (x[3] is None or today < x[3])]
        snapshots.append({
            "date": stamp,
            "candidate_issuer_count_from_vendor_dates": len(candidates),
            "vendor_currently_delisted_but_candidate_at_date": sum(x[4] == "0" for x in candidates),
            "source_datetime_proves_historical_knowledge": False,
            "verified_historical_ST_halt_state": False,
        })
    return main, snapshots

def capture(out, provider, minimum=MIN_MAINBOARD):
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    q = {
        "phase": "P1_BAOSTOCK_LISTING_LIFECYCLE_CANDIDATE_AUDIT",
        "status": "BLOCKED_SOURCE_UNVERIFIED",
        "source": "Baostock query_stock_basic() historical dates",
        "requested_dates": list(DATES),
        "login_attempts": 1, "logical_query_attempts": 0,
        "underlying_protocol_calls_verified": False,
        "vendor_dates_are_retrospective_not_asof": True,
        "source_exchange_authenticated": False,
        "historical_point_in_time_universe_verified": False,
        "historical_ST_halt_delist_verified": False,
        "historical_daily_bar_coverage_verified": False,
        "live_or_backtest_trade_validated": False,
        "paid_api_calls": 0, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }
    logged = False
    try:
        login = provider.login()
        if login.error_code != "0":
            q["provider_login_code"] = str(login.error_code)[:20]
            raise ValueError("Source login failure")
        logged = True
        q["logical_query_attempts"] = 1
        result = provider.query_stock_basic()
        if result.error_code != "0" or tuple(result.fields) != FIELDS:
            q["provider_query_error_code"] = str(result.error_code)[:20]
            raise ValueError("Unexpected provider fields or query failure")
        rows = []
        while result.next():
            rows.append(result.get_row_data())
            if len(rows) > MAX_ROWS:
                raise ValueError("Source row budget exceeded")
        main, snapshots = audit_rows(rows, minimum)
        raw = source_csv(rows)
        fname = "baostock_stock_basic_original.csv"
        (directory / fname).write_bytes(raw)
        q.update(
            status="VENDOR_LIFECYCLE_CANDIDATE_OBSERVED_NOT_OFFICIAL_PIT",
            original_source_rows=len(rows), mainboard_prefix_lifecycles=len(main),
            vendor_currently_delisted_mainboard_rows=sum(x[4] == "0" for x in main),
            source_csv_name=fname, source_csv_sha256=hashlib.sha256(raw).hexdigest(),
            source_csv_bytes=len(raw),
            retrospective_interval_candidates=snapshots,
        )
    except (OSError, ValueError, TypeError, AttributeError, KeyError, OverflowError) as exc:
        q["failure_type"] = type(exc).__name__
    finally:
        if logged:
            try:
                provider.logout()
            except Exception:
                q["logout_failed"] = True
        (directory / "quality.json").write_text(
            json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(q, ensure_ascii=False))
    return 0 if q["status"] == "VENDOR_LIFECYCLE_CANDIDATE_OBSERVED_NOT_OFFICIAL_PIT" else 2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    import baostock as bs
    raise SystemExit(capture(args.out, bs))

if __name__ == "__main__":
    main()
