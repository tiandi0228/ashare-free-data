"""Read-only acquisition of one historical SSE-titled daily halt bulletin mirror.

Research only: the document's title and archive host do NOT independently
authenticate its exchange provenance, first-publication instant, complete
issuer session state, or trade eligibility.
"""
import argparse
import hashlib
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SOURCE_URL = ("https://dataclouds.cninfo.com.cn/sjother/regulatory/2025/"
              "20250818/a2ebc194bcf943b1ab78ac3f83bef57c.pdf")
MAX_BYTES = 4_000_000
CLAIM = {
    "issuer": "sh.600150",
    "bulletin_date": "2025-08-18",
    "issuer_name": "中国船舶",
    "reported_halt_start": "2025-08-13",
    "reported_halt_end": None,
    "reported_reason": "重要公告",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("historical bulletin redirect refused")


def verify_pdf(data):
    if (not isinstance(data, bytes) or len(data) < 3000
            or len(data) > MAX_BYTES or not data.startswith(b"%PDF-")
            or b"%%EOF" not in data[-2048:]):
        raise ValueError("unexpected PDF structure or size")
    return hashlib.sha256(data).hexdigest()


def acquire(*, fetch=None, now=None):
    """Acquire a single bounded mirror URL; record uncertainties explicitly."""
    if fetch is None:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            NoRedirect(),
        )
        def fetch(url):
            req = urllib.request.Request(url, headers={
                "User-Agent": "StockMateP3HistoricalEvidenceResearch/1.0",
                "Accept": "application/pdf",
            })
            with opener.open(req, timeout=25) as response:
                if response.status != 200 or response.geturl() != SOURCE_URL:
                    raise ValueError("unexpected server response")
                return response.read(MAX_BYTES + 1)
    parsed = urlsplit(SOURCE_URL)
    if (parsed.scheme != "https" or parsed.hostname != "dataclouds.cninfo.com.cn"
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("unapproved acquisition origin")
    raw = fetch(SOURCE_URL)
    digest = verify_pdf(raw)
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("capture time must have timezone")
    receipt = {
        "phase": "P3_600150_SSE_TITLED_DAILY_BULLETIN_MIRROR_RESEARCH",
        "source_url": SOURCE_URL,
        "mirrored_source_host": parsed.hostname,
        "source_document_title_claim": "上海证券交易所2025年08月18日股票和可转债停复牌信息",
        "visual_row_claim_unverified_by_byte_parser": CLAIM,
        "original_pdf_sha256": digest,
        "original_pdf_bytes": len(raw),
        "capture_utc_not_first_publication": timestamp.astimezone(timezone.utc).isoformat(),
        "pdf_raw_bytes_sha_replay_verified": True,
        "official_exchange_origin_independently_authenticated": False,
        "historical_first_publication_instant_authenticated": False,
        "official_daily_security_status_certified": False,
        "whole_halt_resume_interval_certified": False,
        "historical_PIT_verified": False,
        "outside_observed_day_trade_state": "UNKNOWN",
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }
    return receipt, raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    receipt, raw = acquire()
    folder = args.output_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (receipt["original_pdf_sha256"] + ".pdf")).write_bytes(raw)
    replay = (folder / (receipt["original_pdf_sha256"] + ".pdf")).read_bytes()
    if verify_pdf(replay) != receipt["original_pdf_sha256"]:
        raise ValueError("written PDF replay mismatch")
    (folder / "receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: receipt[k] for k in (
        "phase", "original_pdf_sha256", "original_pdf_bytes",
        "historical_PIT_verified", "trade_gate")}, sort_keys=True))


if __name__ == "__main__":
    main()
