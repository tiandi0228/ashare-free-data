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
CSV_SHA = "c1e9e5844abed70f2471cb337bf917f584f0029109aac7c0bfb80ae85ad1d188"
SOURCE = Path("evidence/p3_002860")
EXPECTED = {f"2026-{d}": "0" for d in
            ("09-22", "09-23", "09-24", "09-28", "09-29", "09-30",
             "10-08", "10-09", "10-12", "10-13")}
EXPECTED["2026-10-14"] = "1"
NOTICES = (
    ("halt", "043", "09-22", "1225575586", "c478bc5281775db7c7f0fb6e3dcc90d97236244aaf696c5a375bf1eed903b127",
     "自2026年9月22日开市起停牌"),
    ("progress", "044", "09-30", "1225586506", "b910e79f77fb8add770084e477f81083c7f0d7ab7013ffc4ed5994f53c7b49f4",
     "自2026年9月22日开市起停牌"),
    ("resume", "047", "10-14", "1225604019", "4c9fe6862db1119fbe4090f590ff7c00c76d791ece3be58543559a5c82238eee",
     r"将于2026年10月14日[（(]星期三[）)]开市起复牌"),
)


def audit(archive, source=SOURCE):
    if subprocess.check_output(["git", "-C", str(archive), "rev-parse", "HEAD"],
                               text=True).strip() != ARCHIVE:
        raise ValueError("unexpected vendor archive commit")
    shard = archive / "5ba00fbd720fad90/shard_0378"
    if "sz.002860" not in {r["code"] for r in assess(shard)["details"]}:
        raise ValueError("issuer absent from archive receipt")
    raw = (shard / "sz_002860.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CSV_SHA:
        raise ValueError("unexpected vendor CSV hash")
    rows = {r["date"]: r["tradestatus"] for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if "2026-09-22" <= r["date"] <= "2026-10-14"}
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
        if ("股票代码：002860" not in body or f"公告编号：2026-{number}" not in body
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
    return dict(issuer="sz.002860", vendor_csv_sha256=CSV_SHA, archive_commit=ARCHIVE,
                notices=evidence, matched_rows=rows, index_matched=len(index),
                historical_PIT_verified=False, entire_issuer_gap_closed=False,
                trade_gate="BLOCKED", orders=[], executable_candidates=[])


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1])), indent=2))
