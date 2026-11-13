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
CSV_SHA = "cb54189b8e76230ba70324a16fb53c6b316c0ce4c64dd3e2ff066177e82cf08f"
SOURCE = Path("evidence/p3_002813")
EXPECTED = {f"2026-{d}": "0" for d in ("09-30", "10-08", "10-09", "10-12", "10-13")}
EXPECTED["2026-10-14"] = "1"
NOTICES = (
    ("halt", "022", "09-30", "1225589222", "fcce28bc349aeaacc741148048fbac47fdf10136eaaef4c8b24bd3dfcf03aa4c",
     r"2026年9月30日[（(]星期三[）)]开市起停牌"),
    ("progress", "023", "10-09", "1225597548", "272a7d1131f989177b761e41d320868a5bb3a3f61705fe500e3ae61475922239",
     r"2026年10月9日[（(]星期五[）)]开市起继续停牌"),
    ("resume", "025", "10-14", "1225604178", "7b96242a1ccf84f1e5b3aebcacca50b02a44bd0aa7be2d81f7edcc30fffdd6e2",
     r"2026年10月14日[（(]星期三[）)]上午开市起复牌"),
)
SZSE_RESUME_URL = "https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-14/6b255775-6b1f-4f4a-aa78-37830de08dc2.PDF"



def audit(archive, source=SOURCE):
    if subprocess.check_output(["git", "-C", str(archive), "rev-parse", "HEAD"],
                               text=True).strip() != ARCHIVE:
        raise ValueError("unexpected vendor archive commit")
    shard = archive / "5ba00fbd720fad90/shard_0372"
    if "sz.002813" not in {r["code"] for r in assess(shard)["details"]}:
        raise ValueError("issuer absent from archive receipt")
    raw = (shard / "sz_002813.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CSV_SHA:
        raise ValueError("unexpected vendor CSV hash")
    rows = {r["date"]: r["tradestatus"] for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if "2026-09-30" <= r["date"] <= "2026-10-14"}
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
        if ("证券代码：002813" not in body or not re.search(rf"公告编号[:：]2026-{number}", body)
            or not re.search(clause, body)):
            raise ValueError("notice identity or event clause mismatch")
        url = f"https://static.cninfo.com.cn/finalpage/2026-{month_day}/{notice_id}.PDF"
        clock = None
        if notice_id in index:
            entry = index[notice_id]
            if entry["secCode"] != "002813" or "https://static.cninfo.com.cn/" + entry["adjunctUrl"] != url:
                raise ValueError("index URL mismatch")
            millis = entry["announcementTime"]
            if type(millis) is not int:
                raise ValueError("index timestamp must be integer milliseconds")
            instant = datetime.fromtimestamp(millis / 1000, ZoneInfo("Asia/Shanghai"))
            if instant.date().isoformat() != f"2026-{month_day}":
                raise ValueError("index date differs from original path")
            clock = instant.isoformat()
        evidence.append(dict(role=role, notice_number=f"2026-{number}", url=url, sha256=sha,
                             index_clock_beijing_unverified=clock, official_first_release=None,
                             cross_publisher_pdf_url=SZSE_RESUME_URL if role == "resume" else None))
    return dict(issuer="sz.002813", vendor_csv_sha256=CSV_SHA, archive_commit=ARCHIVE,
                notices=evidence, matched_rows=rows, index_matched=len(index),
                historical_PIT_verified=False, entire_issuer_gap_closed=False,
                trade_gate="BLOCKED", orders=[], executable_candidates=[])


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
