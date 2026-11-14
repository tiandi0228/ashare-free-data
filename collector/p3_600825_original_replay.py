"""Replay one source-pinned issuer halt/resume interval, not trading evidence."""
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

from collector.p2_independent_bars import assess, audit_csv

ARCHIVE = "7028eb4c9cc7f23add64958bc6f2611565476538"
SHARD = Path("5ba00fbd720fad90/shard_0078")
SOURCE = Path("evidence/p3_600825_notices")
CODE = "sh.600825"
CSV_SHA = "63ae1dd1502c2340aea79be6144a58d2256ed7edeb8c72b3bc69f289eb673e8a"
NOTICES = (
    ("halt.pdf", "2026-030", "2026-10-13", "停牌", "1225602155",
     "7ed3554376aa8c473180008e06d0f9420016d571d3cf0c5b54af3617b56947a2"),
    ("resume.pdf", "2026-031", "2026-10-16", "复牌", "1225607741",
     "b3895231b55a8fd2b0af26a4e1bd774d0a6de105bc487fa1da1adaff5e483c65"),
)
EXPECTED = {"2026-10-13": "0", "2026-10-14": "0", "2026-10-15": "0", "2026-10-16": "1"}


def verify_notice(raw, spec):
    _, number, effective, action, identifier, sha = spec
    if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("original PDF format or hash mismatch")
    extracted = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "1", "-layout", "-", "-"],
        input=raw, capture_output=True, check=True, timeout=15,
    ).stdout.decode("utf-8")
    normalized = re.sub(r"\s+", "", extracted)
    y, m, d = map(int, effective.split("-"))
    effective_clause = rf"{y}年{m}月{d}日[（(]星期.[）)]开市起{action}"
    if ("证券代码：600825" not in normalized or f"公告编号：{number}" not in normalized
        or not re.search(effective_clause, normalized)
        or (action == "复牌" and "2026/10/152026/10/16" not in normalized)):
        raise ValueError("issuer, announcement or effective clause mismatch")
    return {"number": number, "effective_day": effective, "action": action,
            "url": f"https://static.cninfo.com.cn/finalpage/{effective}/{identifier}.PDF",
            "original_sha256": sha, "first_publication_timestamp_verified": False}


def replay(raw, source=SOURCE):
    receipts = [verify_notice((source / spec[0]).read_bytes(), spec) for spec in NOTICES]
    if hashlib.sha256(raw).hexdigest() != CSV_SHA:
        raise ValueError("original vendor CSV hash mismatch")
    audit_csv(raw, CODE)
    found = {r["date"]: r["tradestatus"] for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
             if r["date"] in EXPECTED}
    if found != EXPECTED:
        raise ValueError("incomplete or conflicting vendor halt interval")
    return {
        "status": "FOUR_ARCHIVED_DAYS_MATCH_ORIGINAL_HALT_RESUME_NOTICES",
        "issuer": CODE, "archive_commit": ARCHIVE, "csv_sha256": CSV_SHA,
        "notices": receipts, "vendor_daily_status": found,
        "matched_days": len(found), "pre_open_availability_verified": False,
        "full_historical_calendar_authenticated": False, "historical_PIT_verified": False,
        "entire_issuer_gap_closed": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    actual = subprocess.check_output(
        ["git", "-C", str(args.archive), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != ARCHIVE:
        raise ValueError("unexpected archive commit")
    shard = args.archive / SHARD
    if CODE not in {item["code"] for item in assess(shard)["details"]}:
        raise ValueError("issuer missing in original shard receipt")
    print(json.dumps(replay((shard / "sh_600825.csv").read_bytes()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
