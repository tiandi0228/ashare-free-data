"""One 600421 two-PDF chronology, externally acquired source digests only.

Both PDF original bytes were obtained from CNINFO on 2026-10-21 and are
NOT reconstructible from repository receipts. This is *not* historical
as-of disclosure availability or complete exchange ST/delist authority.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re

from collector.p3_disclosure_event_ledger import normalize_notice

EARLY_RUN = 39580585146
EARLY_SHA = "ef9b9113b2a51ca718e786de0613860351f0c8056916e7decb5a010da7acaff8"
EARLY_URL = "https://static.cninfo.com.cn/finalpage/2026-05-23/1225327963.PDF"
KNOWN_DAYS = (
    "2026-05-22", "2026-05-23", "2026-05-29", "2026-06-01",
    "2026-06-19", "2026-06-22", "2026-06-26",
)
HASH = re.compile(r"[0-9a-f]{64}\Z")


def ensure(test, reason):
    if not test:
        raise ValueError(reason)


def combine(early_receipt, later_receipt, asof):
    day = date.fromisoformat(asof)
    ensure(asof in KNOWN_DAYS, "Unsupported decision date")
    e = early_receipt
    src = e.get("source_observation", {})
    ensure(e.get("evidence_type") ==
           "DIRECT_CNINFO_ISSUER_EARLY_DELIST_PDF_SHA_RECEIPT_ONLY",
           "Earlier issuer provenance record changed")
    ensure(e.get("acquisition_run_id") == EARLY_RUN and
           e.get("conclusion") == "success" and
           e.get("acquisition_run_sha") ==
           "7e74446c82d4084c3fd4b93c1c7c1b0088d7fc6e",
           "Incorrect original earlier source run")
    ensure(e.get("original_pdf_not_retained_in_repo") is True and
           e.get("original_pdf_sha_does_not_reconstruct_bytes") is True,
           "Original earlier PDF retention unclear")
    ensure(src.get("phase") == "P3_CNINFO_600421_EARLY_DELIST_RISK_PDF" and
           src.get("status") == "ISSUER_EARLY_NOTICE_OBSERVED_UNVERIFIED_PIT" and
           src.get("source_issuer") == "sh.600421",
           "Earlier official disclosure cannot be associated with issuer")
    ensure(src.get("source_url") == EARLY_URL and
           src.get("source_sha256") == EARLY_SHA and
           HASH.fullmatch(src.get("source_sha256", "")) is not None,
           "Original earlier source SHA or URL mismatch")
    ensure(src.get("original_pdf_bytes") == 244242 and
           src.get("original_pdf_pages") == 3 and
           src.get("attempted_https_gets") == 1,
           "Earlier PDF byte/page/request count changed")
    ensure(src.get("url_date") == "2026-05-23" and
           src.get("issuer_stated_resumption_date") == "2026-06-01" and
           src.get("event_type") == "ISSUER_DELISTING_CONSOLIDATION_NOTICE",
           "Earlier issuer chronology changed")
    ensure(src.get("original_issuer_publication_instant_verified") is False and
           src.get("tradability_on_resumption_date_exchange_verified") is False and
           src.get("official_st_status_history_covered") is False and
           src.get("source_pdf_cryptographic_publisher_signature_verified") is False,
           "Early notice incorrectly made official as-of state")
    ensure(src.get("trade_gate") == "BLOCKED" and src.get("orders") == [] and
           src.get("executable_candidates") == [] and src.get("paid_api_calls") == 0,
           "Earlier no-trading invariant broken")
    later = normalize_notice(later_receipt, "2026-06-22")
    ensure(later["trade_gate"] == "BLOCKED" and
           later["source_observed_from_cloud_run"] == 39579302851 and
           later["original_pdf_bytes_archived_here"] is False,
           "Later risk notice original receipt not eligible")
    resume = date.fromisoformat(src["issuer_stated_resumption_date"])
    late_notice = date.fromisoformat(later["issuer_notice_url_calendar_date"])
    expected_last = date.fromisoformat(
        later["non_executable_research_events"][0]["forecast_date"])
    referenced_actual = date.fromisoformat(
        later["non_executable_research_events"][1][
            "claimed_effective_date_for_independent_audit"])
    ensure(date.fromisoformat(src["url_date"]) < resume < late_notice <
           expected_last < referenced_actual,
           "Source chronology invalid")

    return {
        "phase": "P3_CNINFO_TWO_REAL_PDF_ISSUER_EVENT_CHAIN",
        "status": "TWO_ISSUER_DOCUMENT_SHA_RECEIPTS_PIT_BLOCKED",
        "issuer": "sh.600421",
        "decision_date": day.isoformat(),
        "original_source_acquisition_run_ids": [EARLY_RUN, 39579302851],
        "issuer_pdf_sha_receipts": [EARLY_SHA, later["source_sha256"]],
        "original_pdf_raw_bytes_archived_for_replay": False,
        "public_sources_observed_only_in_october_2026": True,
        "historical_release_timestamp_verified": False,
        "event_types": [
            {
                "type": "ISSUER_STATED_RESUMPTION_DATE",
                "source_url_date": "2026-05-23",
                "stated_date": "2026-06-01",
                "actual_exchange_tradability_verified": False,
            },
            {
                "type": "ISSUER_FORECAST_FINAL_TRADING_DATE",
                "source_url_date": "2026-06-19",
                "forecast": "2026-06-22",
                "is_effective_exchange_delist": False,
            },
            {
                "type": "EXCHANGE_EFFECTIVE_DELIST_DATE_AUDIT_REFERENCE_ONLY",
                "reference_effective_date": "2026-06-26",
                "first_party_original_observed_in_runner": False,
                "exchange_original_sha256": None,
            },
        ],
        "historical_asof_document_availability": None,
        "historical_ST_status_verified": False,
        "historical_halt_status_verified": False,
        "historical_exchange_delist_complete": False,
        "tradable_asof_day": None,
        "candidate_universe": [],
        "executable_candidates": [],
        "orders": [],
        "trade_gate": "BLOCKED",
        "paid_api_calls": 0,
        "blockers": [
            "SOURCE_PDF_ORIGINALS_NOT_PRESERVED_FOR_REPLAY",
            "HISTORICAL_ISSUER_PUBLICATION_INSTANT_NOT_AUTHENTICATED",
            "FORECAST_VERSUS_ACTUAL_DELIST_DATE_NOT_INTERCHANGEABLE",
            "OFFICIAL_EXCHANGE_ORIGINAL_DELIST_PAGE_NOT_CAPTURED",
            "FULL_MARKET_ST_HALT_DELIST_PIT_COVERAGE_MISSING",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--early", default="reports/p3_cninfo_600421_early_20261021.json")
    ap.add_argument("--later", default="reports/p3_cninfo_600421_disclosure_pdf_20261021.json")
    ap.add_argument("--asof", required=True, choices=KNOWN_DAYS)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = combine(
        json.loads(Path(args.early).read_text("utf-8")),
        json.loads(Path(args.later).read_text("utf-8")),
        args.asof,
    )
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
