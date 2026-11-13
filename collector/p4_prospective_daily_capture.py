"""Capture one completed Beijing day for the bounded P4 research pilot."""
import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from collector.p2_independent_bars import FIELDS, audit_csv

BEIJING = timezone(timedelta(hours=8))
START, END = date(2026, 12, 1), date(2027, 1, 31)
REGISTRATION = "913889c977ede0d50bb5ecc5f78e0a3516b7d07d53ec4774065a0044dd6cbe0d"
CODES = tuple(f"sh.{code}" for code in (
    "601100", "601101", "601106", "601107", "601108", "601111", "601112", "601113",
))


def eligible_day(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("capture time must be timezone-aware")
    local = now.astimezone(BEIJING)
    if not (START <= local.date() <= END and local.weekday() < 5
            and local.time() >= time(19, 30)):
        return None
    return local.date().isoformat()


def read_day(client, code, day):
    result = client.query_history_k_data_plus(
        code, fields=",".join(FIELDS), start_date=day, end_date=day,
        frequency="d", adjustflag="3",
    )
    if result.error_code != "0" or list(result.fields) != FIELDS:
        raise ValueError("provider query or schema invalid")
    if not result.next():
        if result.error_code != "0":
            raise ValueError("provider row fetch failed")
        return None
    row = list(result.get_row_data())
    if (len(row) != len(FIELDS) or not all(isinstance(x, str) for x in row)
        or row[:2] != [day, code] or result.next() or result.error_code != "0"):
        raise ValueError("expected one matching daily row")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerow(row)
    raw = stream.getvalue().encode("utf-8")
    stats = audit_csv(raw, code)
    if stats["total_rows"] != 1 or stats["first"] != day or stats["last"] != day:
        raise ValueError("daily CSV integrity check failed")
    return raw


def capture(root, now, provider, *, clock=None):
    day = eligible_day(now)
    receipt = {
        "status": "OUTSIDE_CAPTURE_WINDOW", "beijing_day": day,
        "registration_sha256": REGISTRATION,
        "scope": "FIXED_EIGHT_ISSUER_PILOT_NOT_FULL_REGISTERED_COHORT",
        "source": "BaoStock daily unadjusted SDK rows",
        "official_session_verified": False, "prospective_OOS_validated": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "rows": [],
    }
    if day is None:
        return receipt
    # Lock the date directory before provider access so a retry cannot rewrite evidence.
    destination = Path(root) / day
    destination.mkdir(parents=True, exist_ok=False)
    client = provider()
    session = client.login()
    if session.error_code != "0":
        raise RuntimeError("BaoStock login failed")
    try:
        for code in CODES:
            raw = read_day(client, code, day)
            if raw is None:
                receipt["rows"].append({"code": code, "status": "NO_VENDOR_ROW"})
                continue
            filename = code.replace(".", "_") + ".csv"
            (destination / filename).write_bytes(raw)
            receipt["rows"].append({"code": code, "status": "OBSERVED_VENDOR_ROW",
                                    "filename": filename, "sha256": hashlib.sha256(raw).hexdigest()})
    finally:
        client.logout()
    completed = clock() if clock is not None else now
    if eligible_day(completed) != day or completed < now:
        raise RuntimeError("capture crossed the eligible Beijing day boundary")
    observed = sum(r["status"] == "OBSERVED_VENDOR_ROW" for r in receipt["rows"])
    receipt.update(
        status=("PILOT_VENDOR_ROWS_ONLY" if observed == len(CODES) else
                "PARTIAL_VENDOR_ROWS" if observed else "NO_VENDOR_ROWS_NOT_A_CALENDAR_PROOF"),
        rows_observed=observed, expected_issuers=len(CODES),
        capture_started_at_utc=now.astimezone(timezone.utc).isoformat(),
        capture_completed_at_utc=completed.astimezone(timezone.utc).isoformat(),
    )
    (destination / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt



def verify_receipt(destination):
    destination = Path(destination)
    receipt = json.loads((destination / "receipt.json").read_bytes())
    day = destination.name
    start, end = (datetime.fromisoformat(receipt[k]) for k in
                  ("capture_started_at_utc", "capture_completed_at_utc"))
    if (receipt["beijing_day"] != day or eligible_day(start) != day
        or eligible_day(end) != day or end < start
        or receipt["registration_sha256"] != REGISTRATION
        or receipt["trade_gate"] != "BLOCKED" or receipt["orders"] != []
        or receipt["executable_candidates"] != []
        or receipt["prospective_OOS_validated"] is not False
        or receipt["official_session_verified"] is not False):
        raise ValueError("unsafe or mismatched capture receipt")
    if tuple(item["code"] for item in receipt["rows"]) != CODES:
        raise ValueError("wrong pilot coverage")
    files = {"receipt.json"}
    for item in receipt["rows"]:
        if item["status"] == "NO_VENDOR_ROW" and set(item) == {"code", "status"}:
            continue
        filename = item["code"].replace(".", "_") + ".csv"
        if item["status"] != "OBSERVED_VENDOR_ROW" or item["filename"] != filename:
            raise ValueError("invalid daily row receipt")
        raw = (destination / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("daily row SHA mismatch")
        stats = audit_csv(raw, item["code"])
        if stats["total_rows"] != 1 or stats["first"] != day or stats["last"] != day:
            raise ValueError("daily row does not match receipt date")
        files.add(filename)
    count = len(files) - 1
    expected_status = ("PILOT_VENDOR_ROWS_ONLY" if count == len(CODES) else
                       "PARTIAL_VENDOR_ROWS" if count else "NO_VENDOR_ROWS_NOT_A_CALENDAR_PROOF")
    if ({p.name for p in destination.iterdir()} != files
        or receipt["rows_observed"] != count or receipt["expected_issuers"] != len(CODES)
        or receipt["status"] != expected_status):
        raise ValueError("capture inventory mismatch")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    def provider():
        import baostock
        return baostock

    def clock():
        return datetime.now(timezone.utc)
    result = capture(args.out, clock(), provider, clock=clock)
    if result["beijing_day"] is not None:
        result = verify_receipt(args.out / result["beijing_day"])
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, sort_keys=True))


if __name__ == "__main__":
    main()
