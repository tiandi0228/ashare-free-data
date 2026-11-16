"""Audit the CNINFO index clock for the two verified 000582 originals."""
from datetime import datetime, time, timedelta, timezone
import hashlib

from collector.p3_000582_halt_replay import HALT, RESUME, SOURCES

BEIJING = timezone(timedelta(hours=8))
INDEX = {"halt": ("1225591603", HALT), "resume": ("1225599813", RESUME)}
MEDIA = {"resume": {
    "report_date_beijing": "2026-10-11",
    "url": "https://www.bbtnews.com.cn/2026/1011/607565.shtml",
    "precision": "MEDIA_DATE_ONLY",
    "supports": "RESUMPTION_WAS_REPORTED",
}}


def inspect(index_rows, source_pdfs):
    if not isinstance(index_rows, list) or len(index_rows) != 2:
        raise ValueError("expected exactly two bounded CNINFO index rows")
    by_id = {row.get("announcementId"): row for row in index_rows}
    if set(by_id) != {aid for aid, _ in INDEX.values()}:
        raise ValueError("duplicate or unexpected announcement ID")
    report = {}
    for kind, (aid, indexed_day) in INDEX.items():
        row = by_id[aid]
        path = f"finalpage/{indexed_day}/{aid}.PDF"
        stamp_ms = row.get("announcementTime")
        if (row.get("secCode") != "000582" or row.get("orgId") != "gssz0000582"
                or row.get("adjunctUrl") != path or type(stamp_ms) is not int
                or not 0 < stamp_ms < 4102444800000):
            raise ValueError("CNINFO row does not bind to the expected issuer and PDF")
        digest = hashlib.sha256(source_pdfs[kind]).hexdigest()
        if digest != SOURCES[kind][1]:
            raise ValueError("indexed PDF bytes differ from verified original")
        stamp = datetime.fromtimestamp(stamp_ms / 1000, BEIJING)
        if stamp.date().isoformat() != indexed_day:
            raise ValueError("CNINFO calendar value differs from indexed day")
        report[kind] = {
            "announcement_id": aid, "indexed_pdf": "https://static.cninfo.com.cn/" + path,
            "original_sha256": digest, "index_date_beijing": indexed_day,
            "index_value_beijing_not_publication_proof": stamp.isoformat(),
            "index_value_is_midnight": stamp.time() == time.min,
            "storage_time_supplied": row.get("storageTime") is not None,
            "first_publication_time_verified": False,
        }
    return {
        "phase": "P3_000582_PUBLICATION_CLOCK_AUDIT", "notices": report,
        "media_context_not_official_notice_clock": MEDIA["resume"].copy(),
        "index_value_is_not_first_publication_time": True,
        "historical_decision_time_eligibility_verified": False,
        "historical_PIT_verified": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }
