"""Replay two source-pinned issuer halt/resume intervals, not trading evidence."""
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
    ("september-halt.pdf", "2026-014", "2026-09-08", "1225552231",
     "c78991d668b876ef542919f2bbe1265757e667dec9866a18aa3f246f198768fa",
     (r"已于2026年9月7日[（(]星期一[）)]开市起停牌",
      r"2026年9月8日[（(]星期二[）)]开市起继续停牌", "2026/9/8")),
    ("september-resume.pdf", "2026-018", "2026-09-19", "1225571469",
     "9f9745f3b6cad06fdb2d3b7965f7c861eb333e46cdf8fc211322bb1ed699c9ab",
     (r"2026年9月21日[（(]星期一[）)]开市起复牌", "2026/9/182026/9/21")),
    ("halt.pdf", "2026-030", "2026-10-13", "1225602155",
     "7ed3554376aa8c473180008e06d0f9420016d571d3cf0c5b54af3617b56947a2",
     (r"2026年10月13日[（(]星期二[）)]开市起停牌",)),
    ("resume.pdf", "2026-031", "2026-10-16", "1225607741",
     "b3895231b55a8fd2b0af26a4e1bd774d0a6de105bc487fa1da1adaff5e483c65",
     (r"2026年10月16日[（(]星期五[）)]开市起复牌", "2026/10/152026/10/16")),
)
EXPECTED = {
    **{f"2026-09-{day:02}": "0" for day in (*range(7, 12), *range(14, 19))},
    "2026-09-21": "1",
    "2026-10-13": "0", "2026-10-14": "0", "2026-10-15": "0", "2026-10-16": "1",
}
EFFECTIVE = {
    "2026-014": {"retrospective_halt_start": "2026-09-07", "continued_halt": "2026-09-08"},
    "2026-018": {"last_halted_day": "2026-09-18", "resume": "2026-09-21"},
    "2026-030": {"halt_start": "2026-10-13"},
    "2026-031": {"last_halted_day": "2026-10-15", "resume": "2026-10-16"},
}


def verify_notice(raw, spec):
    _, number, url_day, identifier, sha, patterns = spec
    if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("original PDF format or hash mismatch")
    extracted = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=raw, capture_output=True, check=True, timeout=15,
    ).stdout.decode("utf-8")
    normalized = re.sub(r"\s+", "", extracted)
    if ("证券代码：600825" not in normalized or f"公告编号：{number}" not in normalized
        or not all(re.search(pattern, normalized) for pattern in patterns)):
        raise ValueError("issuer, announcement or effective clause mismatch")
    return {"number": number, "event_dates": EFFECTIVE[number],
            "url_path_date_not_timestamp": url_day,
            "url": f"https://static.cninfo.com.cn/finalpage/{url_day}/{identifier}.PDF",
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
        "status": "TWO_HALT_RESUME_INTERVALS_MATCH_ARCHIVED_VENDOR_ROWS",
        "issuer": CODE, "archive_commit": ARCHIVE, "csv_sha256": CSV_SHA,
        "notices": receipts, "vendor_daily_status": found,
        "matched_days": len(found), "pre_open_availability_verified": False,
        "secondary_public_visibility_lead": {
            "event": "2026-09-21_RESUME", "displayed_media_time_beijing": "2026-09-18T19:32:00+08:00",
            "url": "https://www.stcn.com/article/detail/4191231.html",
            "official_first_publication_proof": False,
        },
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
