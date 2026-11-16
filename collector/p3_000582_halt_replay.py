"""Replay a bounded, retrospective halt/resume evidence pair. No PIT promotion."""
import argparse
import csv
from datetime import date
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path

ISSUER = "sz.000582"
SOURCES = {
    "halt": ("https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-08/"
             "4bff47b8-2edf-4822-96ce-ee71323e794c.PDF",
             "e1a2f5d5050c792d4dc3886ba7a9bc5b470535f03a945c77ea657d66949a7394", "2026059"),
    "resume": ("https://static.cninfo.com.cn/finalpage/2026-10-12/1225599813.PDF",
               "07dfb6875c681b3e5c3321100de6c62b41678c6ff617fcb65a2325efbd8fcce0", "2026061"),
}
VENDOR_SHA = "e80eff9f115192df540005f6ca7f519dd3cb8c3728551dbff48679145b03a893"
ARCHIVE_SHA = "9928ba76ceaeac72506a3e6d4af63bac8d98c279"
VENDOR_PATH = "5ba00fbd720fad90/shard_0231/sz_000582.csv"
HALT, RESUME = "2026-10-08", "2026-10-12"
HALT_CLAUSE = "自2026年10月8日（星期四）开市时起开始停牌"
RESUME_CLAUSE = "将于2026年10月12日（星期一）开市起复牌"
EXPECTED_ROWS = [(HALT, "0"), ("2026-10-09", "0"), (RESUME, "1")]


def check_text(halt, resume):
    halt, resume = ("".join(text.split()) for text in (halt, resume))
    for text, kind in ((halt, "halt"), (resume, "resume")):
        if not all(cue in text for cue in ("证券代码：000582", "北部湾港", "公告编号：" + SOURCES[kind][2])):
            raise ValueError("PDF issuer or announcement number differs")
    if HALT_CLAUSE not in halt or HALT_CLAUSE not in resume or RESUME_CLAUSE not in resume:
        raise ValueError("PDF effective clauses do not corroborate the pair")


def check_rows(raw):
    rows = list(csv.DictReader(StringIO(raw.decode("utf-8-sig"))))
    dates = [date.fromisoformat(row["date"]) for row in rows]
    if dates != sorted(set(dates)) or any(row["code"] != ISSUER for row in rows):
        raise ValueError("unexpected issuer or unordered vendor rows")
    observed = [(row["date"], row["tradestatus"]) for row in rows if HALT <= row["date"] <= RESUME]
    if observed != EXPECTED_ROWS:
        raise ValueError("original vendor statuses do not match bounded evidence")
    return observed


def replay(halt, resume, vendor):
    from pypdf import PdfReader

    evidence = {}
    texts = []
    for kind, raw in (("halt", halt), ("resume", resume)):
        url, expected, notice = SOURCES[kind]
        if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"{kind} official PDF SHA mismatch")
        texts.append("".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages))
        evidence[kind] = dict(url=url, sha256=expected, announcement_number=notice)
    check_text(*texts)
    if hashlib.sha256(vendor).hexdigest() != VENDOR_SHA:
        raise ValueError("original vendor CSV SHA mismatch")
    observed = check_rows(vendor)
    return dict(phase="P3_BOUNDED_OFFICIAL_TEXT_VENDOR_STATUS_MATCH", issuer=ISSUER,
                halt_text_date=HALT, resume_text_date=RESUME, official_originals=evidence,
                vendor_archive_commit=ARCHIVE_SHA, vendor_csv_sha256=VENDOR_SHA,
                matched_vendor_rows=[dict(date=day, tradestatus=status) for day, status in observed],
                first_publication_time_verified=False, historical_PIT_verified=False,
                full_halt_interval_certified=False, p2_feature_gaps_resolved=0,
                trade_gate="BLOCKED", orders=[], executable_candidates=[])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("halt", "resume", "vendor", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    result = replay(a.halt.read_bytes(), a.resume.read_bytes(), a.vendor.read_bytes())
    with a.out.open("x", encoding="utf8") as dst:
        dst.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
