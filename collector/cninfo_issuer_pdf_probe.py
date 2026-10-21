"""One bounded official disclosure-platform PDF: issuer risk, not exchange-signed PIT.

CNINFO issuer PDF dated 2026-06-19 discusses an *expected* last trading day.
Never transform predicted final trading day into a definitive delisting date.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

URL = "https://static.cninfo.com.cn/finalpage/2026-06-19/1225377517.PDF"
MAX_BYTES = 3_000_000
MAX_PAGES = 12


def fetch_pdf(url):
    req = Request(url, headers={
        "User-Agent": "ashare-free-data-source-audit/1.0",
        "Accept-Encoding": "identity",
    })
    with urlopen(req, timeout=16) as response:
        if response.geturl() != URL:
            raise ValueError("Unexpected disclosure PDF redirect")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("PDF exceeds frozen byte budget")
        return body, response.geturl()


def extract_pdf_text(raw):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("PDF page count exceeds frozen bound")
    text = "".join((page.extract_text() or "") for page in reader.pages)
    return text, len(reader.pages)


def inspect_pdf(raw, final_url, text, pages):
    if final_url != URL:
        raise ValueError("Disclosure URL mismatch")
    if len(raw) > MAX_BYTES or not raw.startswith(b"%PDF-"):
        raise ValueError("Source is not a bounded PDF")
    if not isinstance(pages, int) or not 1 <= pages <= MAX_PAGES:
        raise ValueError("Invalid page count")
    normalized = re.sub(r"\s+", "", text)
    anchors = (
        "湖北华嵘控股股份有限公司",
        "600421",
        "退市整理期",
        "2026年6月22日",
    )
    if not all(phrase in normalized for phrase in anchors):
        raise ValueError("Issuer/date/risk-warning content anchors absent")
    return {
        "source_url": final_url,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "pdf_pages": pages,
        "document_url_dated": "2026-06-19",
        "issuer": "sh.600421",
        "notice_category": "ISSUER_DELISTING_RISK_NOTICE",
        "risk_notice_expected_last_trading_date": "2026-06-22",
        "actual_exchange_delist_effective_date_verified_from_this_pdf": False,
        "official_exchange_listing_decision_verified_from_this_pdf": False,
        "source_document_cryptographically_signed_verified": False,
        "historical_asof_publication_timestamp_verified": False,
        "source_pdf_not_redistributed": True,
    }


def capture(out, fetch=fetch_pdf, extract=extract_pdf_text):
    path = Path(out)
    path.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "P3_CNINFO_ISSUER_PDF_ONE_SOURCE_PROBE",
        "status": "BLOCKED_NO_SOURCE",
        "requested_url": URL,
        "attempted_gets": 1,
        "exchange_publisher_identity_signed": False,
        "historical_point_in_time_universe_verified": False,
        "historical_ST_halt_delist_complete": False,
        "broker_trade_permissions": False,
        "paid_api_calls": 0,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }
    try:
        raw, final_url = fetch(URL)
        page_text, pages = extract(raw)
        data = inspect_pdf(raw, final_url, page_text, pages)
        report.update(data)
        report["status"] = "ISSUER_DISCLOSURE_SOURCE_OBSERVED_NOT_EXCHANGE_PIT"
    except (ValueError, OSError, UnicodeError, TimeoutError, TypeError, KeyError) as exc:
        report["failure_type"] = type(exc).__name__
    report["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    (path / "quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "ISSUER_DISCLOSURE_SOURCE_OBSERVED_NOT_EXCHANGE_PIT" else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    raise SystemExit(capture(args.out))


if __name__ == "__main__":
    main()
