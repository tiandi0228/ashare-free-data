"""Fail-closed independent recheck of extracted P3 600150 original PDF artifact.

This verifies byte integrity, not publisher, publication time, PIT status or fills.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "1224387134": ("halt", "2025-059", "https://static.cninfo.com.cn/finalpage/2025-08-05/1224387134.PDF"),
    "1224504273": ("resume", "2025-063", "https://static.cninfo.com.cn/finalpage/2025-08-19/1224504273.PDF"),
}
SOURCE = "5be9d6ad76d8635defe02f8d90bc50ad4c03c086"
CSV_SHA = "45bb1574dc7068d696d74bfb74491984a9c792444396f3be6f04abe295ed7c40"


def recheck(folder):
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("artifact directory invalid")
    receipt = folder / "receipt.json"
    if not receipt.is_file() or receipt.is_symlink() or receipt.stat().st_size > 100000:
        raise ValueError("receipt missing or oversized")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any((
        data.get("phase") != "P3_600150_TWO_CNINFO_ORIGINAL_RESEARCH_ACQUISITION",
        data.get("source_issuer") != "sh.600150",
        data.get("frozen_vendor_source_commit") != SOURCE,
        data.get("frozen_vendor_csv_sha256") != CSV_SHA,
        type(data.get("documents_attempted")) is not int or data["documents_attempted"] != 2,
        type(data.get("documents_pdf_sha_replayed")) is not int or data["documents_pdf_sha_replayed"] != 2,
        data.get("research_only_not_certified") is not True,
        data.get("originals_in_immutable_git_archive") is not False,
        data.get("trade_gate") != "BLOCKED",
        data.get("orders") != [],
        data.get("executable_candidates") != [],
        type(data.get("broker_fills_verified")) is not int or data["broker_fills_verified"] != 0,
        any(data.get(k) is not False for k in (
            "official_first_publication_authenticated", "official_halt_resume_interval_certified",
            "official_historical_PIT_verified", "trading_calendar_verified")),
    )):
        raise ValueError("unsafe research receipt")
    rows = data.get("documents")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError("wrong document count")
    allowed = {receipt, folder / "originals"}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid document")
        identifier = row.get("announcement_id")
        if identifier not in EXPECTED or identifier in seen:
            raise ValueError("unexpected or duplicate announcement")
        seen.add(identifier)
        role, number, url = EXPECTED[identifier]
        digest, size = row.get("pdf_sha256"), row.get("original_pdf_bytes")
        if any((
            row.get("issuer") != "sh.600150",
            row.get("document_role") != role,
            row.get("notice_number_claimed") != number,
            row.get("requested_url") != url,
            row.get("status") != "ORIGINAL_BYTES_SHA_REPLAY_VERIFIED_RESEARCH_ONLY",
            not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None,
            type(size) is not int or not 3000 <= size <= 4000000,
            any(row.get(k) is not False for k in (
                "first_publication_authenticated",
                "official_publisher_authenticated_independently",
                "historical_effective_date_authenticated")),
        )):
            raise ValueError("untrusted PDF metadata")
        name = f"originals/sh_600150_{identifier}_{digest}.pdf"
        if row.get("original_artifact_path") != name:
            raise ValueError("PDF identity path mismatch")
        pdf = folder / name
        if not pdf.is_file() or pdf.is_symlink() or pdf.stat().st_size != size:
            raise ValueError("PDF missing or size mismatch")
        raw = pdf.read_bytes()
        if (not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]
                or hashlib.sha256(raw).hexdigest() != digest):
            raise ValueError("PDF original integrity mismatch")
        allowed.add(pdf)
    if set(folder.rglob("*")) != allowed or seen != set(EXPECTED):
        raise ValueError("missing/extra files or symlink")
    return {
        "phase": "P3_600150_INDEPENDENT_ARTIFACT_RECHECK",
        "verified_originals": 2,
        "verified_bytes": sum(r["original_pdf_bytes"] for r in rows),
        "official_first_publication_authenticated": False,
        "official_historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(recheck(args.artifact_dir), sort_keys=True))
