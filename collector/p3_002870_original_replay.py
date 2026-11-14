"""Scoped issuer notice and archived vendor status replay. No PIT certification."""
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

from collector.p2_independent_bars import assess

ARCHIVE = "7028eb4c9cc7f23add64958bc6f2611565476538"
CSV_SHA = "9f69a30a532df4e4178109d0c886f30c82e1f8fd1cf9e0fb3693f13582d3935a"
SOURCE = Path("evidence/p3_002870")
EXPECTED = {f"2026-09-{d:02}": "0" for d in (*range(1, 5), *range(7, 12), 14)}
EXPECTED["2026-09-15"] = "1"
NOTICES = (
    ("halt", "068", "09-01", "1225538772", "feb71e43cf225f48508df3bc9718fd224a7d33bd544cacd5a39ff939c96bdb2e",
     r"自2026年9月1日开市起停牌"),
    ("progress", "069", "09-08", "1225550443", "3e354678459045d14ab494f7d5ee7bc83698a17c98adece3db6a5972de91c09b",
     r"公司股票继续停牌"),
    ("resume", "073", "09-15", "1225563563", "b0ee0cf083b2f2ee7e4d74af51b1c4f367eb611b0791024a8dbc6d2cfed9167f",
     r"将于2026年9月15日[（(]星期二[）)]开市起复牌"),
)



def audit(archive, source=SOURCE):
    if subprocess.check_output(["git", "-C", str(archive), "rev-parse", "HEAD"],
                               text=True).strip() != ARCHIVE:
        raise ValueError("unexpected vendor archive commit")
    shard = archive / "5ba00fbd720fad90/shard_0379"
    if "sz.002870" not in {r["code"] for r in assess(shard)["details"]}:
        raise ValueError("issuer absent from archive receipt")
    raw = (shard / "sz_002870.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CSV_SHA:
        raise ValueError("unexpected vendor CSV hash")
    rows = {r["date"]: r["tradestatus"] for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if "2026-09-01" <= r["date"] <= "2026-09-15"}
    if rows != EXPECTED:
        raise ValueError("archived interval status mismatch")
    observed = json.loads((source / "index.json").read_bytes())
    index = {r["announcementId"]: r for r in observed}
    if len(index) != len(observed) or index.keys() != {spec[3] for spec in NOTICES}:
        raise ValueError("unexpected index inventory")
    evidence = []
    for role, number, month_day, notice_id, sha, clause in NOTICES:
        pdf = (source / (role + ".pdf")).read_bytes()
        if not pdf.startswith(b"%PDF-") or hashlib.sha256(pdf).hexdigest() != sha:
            raise ValueError("unexpected original PDF")
        body = re.sub(r"\s+", "", subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf,
                      capture_output=True, check=True, timeout=15).stdout.decode())
        if ("证券代码：002870" not in body or not re.search(rf"公告编号[:：]2026-{number}", body)
            or not re.search(clause, body)):
            raise ValueError("notice identity or event clause mismatch")
        url = f"https://static.cninfo.com.cn/finalpage/2026-{month_day}/{notice_id}.PDF"
        clock = None
        if notice_id in index:
            entry = index[notice_id]
            if entry["secCode"] != "002870" or "https://static.cninfo.com.cn/" + entry["adjunctUrl"] != url:
                raise ValueError("index URL mismatch")
            millis = entry["announcementTime"]
            if type(millis) is not int:
                raise ValueError("index timestamp must be integer milliseconds")
            instant = datetime.fromtimestamp(millis / 1000, ZoneInfo("Asia/Shanghai"))
            if instant.date().isoformat() != f"2026-{month_day}":
                raise ValueError("index date differs from original path")
            clock = instant.isoformat()
        evidence.append(dict(role=role, notice_number=f"2026-{number}", url=url, sha256=sha,
                             index_clock_beijing_unverified=clock, official_first_release=None))
    return dict(issuer="sz.002870", vendor_csv_sha256=CSV_SHA, archive_commit=ARCHIVE,
                notices=evidence, matched_rows=rows, index_matched=len(index),
                historical_PIT_verified=False, entire_issuer_gap_closed=False,
                trade_gate="BLOCKED", orders=[], executable_candidates=[])


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
