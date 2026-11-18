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
CSV_SHA = "d7d67226a1430bc3c0a56a4e48f08871f1a6dfb996043cc8f6d5c1523a6d60f5"
SOURCE = Path("evidence/p3_603400")
EXPECTED = {f"2026-09-{d:02}": "0" for d in (*range(15, 19), *range(21, 25), 28, 29)}
EXPECTED["2026-09-30"] = "1"
NOTICES = (
    ("halt", "047", "09-15", "1225564363", "0470bfc37fd5e9e87665485d1af64c631cb920050bf88021a840656b18cd7e5f",
     r"2026年9月15日[（(]星期二[）)]开市起开始停牌"),
    ("progress", "048", "09-22", "1225573898", "5340cd1eeeaf0384177f05a4729b301cfbd83a98e36b5b5ab38ee84b94c5ff2c",
     r"公司股票将继续停牌"),
    ("resume", "051", "09-30", "1225588894", "9d13172940225aa643dccd5a26278050d7b689ea5a0bb823044ab9d765f71395",
     r"将于2026年9月30日[（(]星期三[）)]上午开市起复牌"),
)



def audit(archive, source=SOURCE):
    if subprocess.check_output(["git", "-C", str(archive), "rev-parse", "HEAD"],
                               text=True).strip() != ARCHIVE:
        raise ValueError("unexpected vendor archive commit")
    shard = archive / "5ba00fbd720fad90/shard_0161"
    if "sh.603400" not in {r["code"] for r in assess(shard)["details"]}:
        raise ValueError("issuer absent from archive receipt")
    raw = (shard / "sh_603400.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CSV_SHA:
        raise ValueError("unexpected vendor CSV hash")
    rows = {r["date"]: r["tradestatus"] for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if "2026-09-15" <= r["date"] <= "2026-09-30"}
    if rows != EXPECTED:
        raise ValueError("archived interval status mismatch")
    observed = json.loads((source / "index.json").read_bytes())
    index = {r["announcement_id"]: r for r in observed}
    if len(index) != len(observed) or index.keys() != {spec[3] for spec in NOTICES}:
        raise ValueError("unexpected index inventory")
    evidence = []
    for role, number, month_day, notice_id, sha, clause in NOTICES:
        pdf = (source / (role + ".pdf")).read_bytes()
        if not pdf.startswith(b"%PDF-") or hashlib.sha256(pdf).hexdigest() != sha:
            raise ValueError("unexpected original PDF")
        body = re.sub(r"\s+", "", subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf,
                      capture_output=True, check=True, timeout=15).stdout.decode())
        if ("证券代码：603400" not in body or f"公告编号：2026-{number}" not in body
            or not re.search(clause, body)):
            raise ValueError("notice identity or event clause mismatch")
        url = f"https://static.cninfo.com.cn/finalpage/2026-{month_day}/{notice_id}.PDF"
        clock = None
        if notice_id in index:
            entry = index[notice_id]
            if entry["official_pdf_url"] != url:
                raise ValueError("index URL mismatch")
            millis = entry["index_published_milliseconds_unverified"]
            if type(millis) is not int:
                raise ValueError("index timestamp must be integer milliseconds")
            instant = datetime.fromtimestamp(millis / 1000, ZoneInfo("Asia/Shanghai"))
            if instant.date().isoformat() != f"2026-{month_day}":
                raise ValueError("index date differs from original path")
            clock = instant.isoformat()
        evidence.append(dict(role=role, notice_number=f"2026-{number}", url=url, sha256=sha,
                             index_clock_beijing_unverified=clock, official_first_release=None))
    return dict(issuer="sh.603400", vendor_csv_sha256=CSV_SHA, archive_commit=ARCHIVE,
                notices=evidence, matched_rows=rows, index_matched=len(index),
                historical_PIT_verified=False, entire_issuer_gap_closed=False,
                trade_gate="BLOCKED", orders=[], executable_candidates=[])


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
