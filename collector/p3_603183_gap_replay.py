"""Reconcile one real vendor gap with notice-index dates, without certifying PIT."""
import argparse
import csv
import hashlib
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

from collector.p2_independent_bars import assess, audit_csv
from collector.p34_notice_bound_replay import reconcile_halt

ARCHIVE = "7028eb4c9cc7f23add64958bc6f2611565476538"
SHARD = Path("5ba00fbd720fad90/shard_0140")
CODE = "sh.603183"
CSV_SHA = "3f53cf0bd447c2d757488614b4236632069885e793ee04959ae0c888c614168c"
SSE_INDEX = "https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=603183&tabActive=1"
NOTICES = (
    ("2026-021", "2026-09-30", "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-09-30/603183_20260930_U9I2.pdf"),
    ("2026-022", "2026-10-09", "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-10-09/603183_20261009_P35A.pdf"),
)


def reconcile(raw, calendar_root=Path(".")):
    if hashlib.sha256(raw).hexdigest() != CSV_SHA:
        raise ValueError("unexpected archived 603183 original")
    audit_csv(raw, CODE)
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    start, resume = NOTICES[0][1], NOTICES[1][1]
    result = reconcile_halt(
        market="SH", as_of=resume, halt_start=start, resume_day=resume,
        vendor_status={r["date"]: r["tradestatus"] for r in rows if start <= r["date"] <= resume},
        root=calendar_root,
    )
    outcomes = Counter(row["outcome"] for row in result["rows"])
    matched = outcomes == {"MATCH": 3, "SCHEDULED_CLOSURE": 7}
    return {
        **result,
        "status": ("VENDOR_ROWS_MATCH_RESEARCH_INTERVAL_ORIGINAL_NOTICES_PENDING" if matched
                   else "SCOPED_VENDOR_INTERVAL_UNRESOLVED"),
        "issuer": CODE, "archive_commit": ARCHIVE, "vendor_csv_sha256": CSV_SHA,
        "official_notice_index": SSE_INDEX,
        "notice_candidates": [
            {"announcement": n, "displayed_day": d, "original_url": url,
             "original_pdf_verified": False, "original_pdf_sha256": None}
            for n, d, url in NOTICES
        ],
        "outcome_counts": dict(outcomes), "historical_PIT_verified": False,
        "announcement_available_before_open_verified": False,
        "p2_gap_closed": False, "executable_candidates": [],
    }


def from_archive(root):
    root = Path(root)
    actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if actual != ARCHIVE:
        raise ValueError("unexpected archive commit")
    checked = assess(root / SHARD)
    if CODE not in {row["code"] for row in checked["details"]}:
        raise ValueError("issuer missing in shard receipt")
    return reconcile((root / SHARD / "sh_603183.csv").read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(from_archive(args.archive), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
