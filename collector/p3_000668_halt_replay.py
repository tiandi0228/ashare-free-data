"""Cross-check Rongfeng halt/resume notices against pinned vendor bars."""
import csv
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import sys
import unicodedata

ISSUER = "sz.000668"
ARCHIVE = "7129bdd738de2030c2bd40cb5fa05c1d654fbd8d"
CSV_SHA = "44a4551b69866385f224f731b02467f205613cd9e5c93cb7d1b7e5acfeba1231"
HALT_URL = "https://static.cninfo.com.cn/finalpage/2026-10-08/1225591961.PDF"
RESUME_URL = ("https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-13/"
              "a94b3320-be06-43d5-bbff-19649a5c627e.PDF")
EXPECTED = [
    ("2026-10-08", "0"), ("2026-10-09", "0"), ("2026-10-12", "0"), ("2026-10-13", "1"),
]


def compact(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def check_notices(halt, resume):
    halt, resume = compact(halt), compact(resume)
    for text, notice in ((halt, "2026-064"), (resume, "2026-066")):
        if ("证券代码:000668" not in text or "证券简称:荣丰控股" not in text
                or "公告编号:" + notice not in text):
            raise ValueError("wrong issuer or announcement number")
    for text, day, action in ((halt, 8, "停牌"), (resume, 12, "继续停牌"), (resume, 13, "复牌")):
        pattern = rf"自2026年10月{day}日(?:\([^)]{{1,8}}\))?(?:上午)?开市(?:时)?起{action}"
        if not re.search(pattern, text):
            raise ValueError(f"absence of exact effective-date clause: {day} {action}")


def check_vendor(raw):
    rows = list(csv.DictReader(StringIO(raw.decode("utf-8-sig"))))
    if any(r["code"] != ISSUER for r in rows):
        raise ValueError("wrong vendor issuer")
    found = [(r["date"], r["tradestatus"]) for r in rows if EXPECTED[0][0] <= r["date"] <= EXPECTED[-1][0]]
    if found != EXPECTED:
        raise ValueError("vendor statuses do not match the bounded halt and resume sequence")
    return found


def replay(halt, resume, vendor):
    from pypdf import PdfReader

    def extract(raw):
        if not raw.startswith(b"%PDF-") or not 3000 <= len(raw) <= 4 * 1024 * 1024:
            raise ValueError("unexpected original PDF bytes")
        reader = PdfReader(BytesIO(raw))
        if not 1 <= len(reader.pages) <= 12:
            raise ValueError("unexpected original PDF page count")
        return "".join(page.extract_text() or "" for page in reader.pages)

    if hashlib.sha256(vendor).hexdigest() != CSV_SHA:
        raise ValueError("vendor CSV digest differs from the P2 archive")
    check_notices(extract(halt), extract(resume))
    rows = check_vendor(vendor)
    return {
        "phase": "P3_BOUNDED_OFFICIAL_TEXT_VENDOR_STATUS_MATCH",
        "issuer": ISSUER, "archive_commit": ARCHIVE, "vendor_csv_sha256": CSV_SHA,
        "notice_originals": [
            {"url": url, "announcement_number": number, "observed_pdf_sha256": hashlib.sha256(raw).hexdigest()}
            for url, number, raw in ((HALT_URL, "2026-064", halt), (RESUME_URL, "2026-066", resume))
        ],
        "matched_vendor_rows": [{"date": day, "tradestatus": status} for day, status in rows],
        "first_publication_time_verified": False, "full_halt_interval_certified": False,
        "historical_PIT_verified": False, "p2_feature_gaps_resolved": 0,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


if __name__ == "__main__":
    halt, resume, vendor, output = map(Path, sys.argv[1:])
    report = replay(halt.read_bytes(), resume.read_bytes(), vendor.read_bytes())
    with output.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
