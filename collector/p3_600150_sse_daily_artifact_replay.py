"""Independently replay the frozen 2025-08-18 SSE-titled research artifact.

This proves the ZIP, exact PDF bytes and receipt consistency only, never
original SSE provenance, historical first publication, or PIT tradability.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from collector.p3_600150_sse_daily_bulletin_mirror import SOURCE_URL, CLAIM, verify_pdf

ARTIFACT_SHA256 = "313430fe462d98307a7474f17b28bdff7cef8bced313077c31be97b772c55b07"
PDF_SHA256 = "9051ffc0413331c7864c78e6066e57ad2d18c026c48a4c5fed4aae828c758d16"
PDF_BYTES = 34854
ZIP_MAX_BYTES = 1000000
RECEIPT_MAX_BYTES = 20000


def replay(path, *, pinned_zip_sha=ARTIFACT_SHA256):
    path = Path(path)
    if (not path.is_file() or path.is_symlink()
        or path.stat().st_size > ZIP_MAX_BYTES or path.stat().st_size < 500):
        raise ValueError("missing or oversized source artifact")
    archive_bytes = path.read_bytes()
    if hashlib.sha256(archive_bytes).hexdigest() != pinned_zip_sha:
        raise ValueError("source artifact ZIP checksum mismatch")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        expected = {"receipt.json", f"{PDF_SHA256}.pdf"}
        if len(members) != 2 or {x.filename for x in members} != expected:
            raise ValueError("missing/extra/duplicated archive members")
        for member in members:
            if (member.is_dir() or member.file_size > 100000 or
                ((member.external_attr >> 16) & 0o170000) == 0o120000
                or member.filename.startswith("/") or ".." in Path(member.filename).parts):
                raise ValueError("unsafe ZIP entry")
        receipt_bytes = archive.read("receipt.json")
        if len(receipt_bytes) > RECEIPT_MAX_BYTES:
            raise ValueError("oversized receipt")
        receipt = json.loads(receipt_bytes)
        raw = archive.read(f"{PDF_SHA256}.pdf")
    if len(raw) != PDF_BYTES or verify_pdf(raw) != PDF_SHA256:
        raise ValueError("PDF original changed")
    if not isinstance(receipt, dict):
        raise ValueError("invalid receipt")
    expected_values = {
        "phase": "P3_600150_SSE_TITLED_DAILY_BULLETIN_MIRROR_RESEARCH",
        "source_url": SOURCE_URL,
        "mirrored_source_host": "dataclouds.cninfo.com.cn",
        "source_document_title_claim": "上海证券交易所2025年08月18日股票和可转债停复牌信息",
        "visual_row_claim_unverified_by_byte_parser": CLAIM,
        "original_pdf_sha256": PDF_SHA256,
        "original_pdf_bytes": PDF_BYTES,
        "pdf_raw_bytes_sha_replay_verified": True,
        "official_exchange_origin_independently_authenticated": False,
        "historical_first_publication_instant_authenticated": False,
        "official_daily_security_status_certified": False,
        "whole_halt_resume_interval_certified": False,
        "historical_PIT_verified": False,
        "outside_observed_day_trade_state": "UNKNOWN",
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    for key, expected_value in expected_values.items():
        if type(receipt.get(key)) is not type(expected_value) or receipt.get(key) != expected_value:
            raise ValueError("altered receipt or forged status: " + key)
    observed = receipt.get("capture_utc_not_first_publication")
    if (not isinstance(observed, str)
        or not re.fullmatch(r"2026-11-12T[0-9:.]+\+00:00", observed)):
        raise ValueError("capture time cannot be authenticated first-publication")
    return {
        "phase": "P3_600150_DAILY_MIRROR_INDEPENDENT_REPLAY",
        "pdf_sha256": PDF_SHA256,
        "pdf_bytes_verified": PDF_BYTES,
        "visual_claim_parsed_and_certified": False,
        "official_exchange_origin_authenticated": False,
        "first_publication_authenticated": False,
        "official_session_status_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.zip), sort_keys=True))
