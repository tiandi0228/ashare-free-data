"""P3 dated disclosure ledger from a previously verified *single* real PDF receipt.

This ledger intentionally DOES NOT infer official delisting state, historical
as-of publication timestamp, or executable securities from retrospectively
recovered issuer notices. All conclusions remain RESEARCH-ONLY / BLOCKED.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re

ISSUER = "sh.600421"
KNOWN_RUN = 39579302851
KNOWN_RUN_SHA = "1e41280bdbb2f69c3e62990b3d709b3f051db7ac"
KNOWN_ORIGINAL_SHA = "6e43f458ee70b11dc5ab7331c2d67dee62dc26fa2121e138a2c93ef71c65409f"
SOURCE_URL = "https://static.cninfo.com.cn/finalpage/2026-06-19/1225377517.PDF"
SSE_EFFECTIVE_URL = (
    "https://www.sse.com.cn/disclosure/announcement/listing/stock/"
    "c/c_20260622_10823158.shtml"
)
DATES = ("2026-06-18", "2026-06-19", "2026-06-20", "2026-06-22", "2026-06-26")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(assertion, reason):
    if not assertion:
        raise ValueError(reason)


def normalize_notice(receipt, query_date):
    """No market-data requests; consumes actual proven SHA-only receipt."""
    day = date.fromisoformat(query_date)
    require(query_date in DATES, "Decision day not covered by frozen study")
    require(receipt.get("evidence_type") ==
            "DIRECT_CNINFO_ISSUER_DISCLOSURE_PDF_SOURCE_SHA_RECEIPT_ONLY",
            "Receipt is not a real PDF acquisition")
    require(receipt.get("acquisition_run_id") == KNOWN_RUN and
            receipt.get("acquisition_run_sha") == KNOWN_RUN_SHA and
            receipt.get("acquisition_conclusion") == "success",
            "Unexpected cloud acquisition identity")
    p = receipt.get("original_pdf_report", {})
    require(receipt.get("original_pdf_bytes_stored_in_public_repo") is False and
            receipt.get("sha_receipt_cannot_reconstruct_original_bytes") is True,
            "Original source retention scope changed")
    require(p.get("phase") == "P3_CNINFO_ISSUER_PDF_ONE_SOURCE_PROBE" and
            p.get("status") == "ISSUER_DISCLOSURE_SOURCE_OBSERVED_NOT_EXCHANGE_PIT",
            "Issuer original capture not verified")
    require(p.get("issuer") == ISSUER and p.get("source_url") == SOURCE_URL and
            p.get("requested_url") == SOURCE_URL, "Issuer provenance changed")
    require(p.get("source_sha256") == KNOWN_ORIGINAL_SHA and
            SHA.fullmatch(p.get("source_sha256", "")), "Source PDF hash changed")
    require(p.get("source_bytes") == 109614 and p.get("pdf_pages") == 3 and
            p.get("attempted_gets") == 1,
            "Original source size/budget changed")
    require(p.get("document_url_dated") == "2026-06-19" and
            p.get("risk_notice_expected_last_trading_date") == "2026-06-22",
            "Estimated event-date statement changed")
    require(p.get("notice_category") == "ISSUER_DELISTING_RISK_NOTICE",
            "Issuer notice type changed")
    require(p.get("actual_exchange_delist_effective_date_verified_from_this_pdf") is False and
            p.get("official_exchange_listing_decision_verified_from_this_pdf") is False and
            p.get("source_document_cryptographically_signed_verified") is False and
            p.get("historical_asof_publication_timestamp_verified") is False,
            "Source evidence falsely elevated to official PIT")
    require(p.get("paid_api_calls") == 0 and
            p.get("trade_gate") == "BLOCKED" and
            p.get("orders") == [] and p.get("executable_candidates") == [],
            "Original-source no-trade gate changed")
    require(receipt.get("sse_original_sha_not_obtained") is True and
            receipt.get("known_official_sse_effective_delist_web_url") == SSE_EFFECTIVE_URL,
            "Unverified SSE follow-up changed")

    risk_statement_day = date.fromisoformat(p["document_url_dated"])
    expectation_day = date.fromisoformat(p["risk_notice_expected_last_trading_date"])
    # An issuer's forecast cannot become a confirmed last trading day.
    # The original web retrieval happened in October; the June URL path
    # alone cannot establish historical data availability on June 19.
    return {
        "phase": "P3_PIT_DISCLOSURE_EVENT_LEDGER",
        "status": "QUARANTINED_UNVERIFIED_HISTORICAL_ASOF",
        "issuer": ISSUER,
        "decision_date": day.isoformat(),
        "source_observed_from_cloud_run": KNOWN_RUN,
        "source_sha256": KNOWN_ORIGINAL_SHA,
        "original_pdf_bytes_archived_here": False,
        "issuer_notice_url_calendar_date": risk_statement_day.isoformat(),
        "issuer_notice_actual_release_instant_verified": False,
        "content_could_have_been_observed_as_of_day": None,
        "known_historical_asof": False,
        "non_executable_research_events": [
            {
                "kind": "ISSUER_EXPECTED_FINAL_TRADING_DATE",
                "forecast_date": expectation_day.isoformat(),
                "source_type": "CNINFO_ISSUER_RISK_NOTICE",
                "observation_time_authenticated": False,
                "is_actual_delisting_effective_date": False,
                "is_exchange_verified_status": False,
            },
            {
                "kind": "EXCHANGE_ACTUAL_DELISTING_NOTICE_LINK_ONLY",
                "web_reference_url": SSE_EFFECTIVE_URL,
                "claimed_effective_date_for_independent_audit": "2026-06-26",
                "original_exchange_document_sha256": None,
                "source_observed_from_cloud_run": None,
                "accepted_as_verified_trading_state": False,
            },
        ],
        "historical_listing_membership_verified": False,
        "historical_ST_halt_delist_complete": False,
        "issuer_tradable_as_of_day": None,
        "candidate_universe": [],
        "executable_candidates": [],
        "orders": [],
        "trade_gate": "BLOCKED",
        "paid_api_calls": 0,
        "blocking_reasons": [
            "ISSUER_FORECAST_NOT_EFFECTIVE_EXCHANGE_DATE",
            "ORIGINAL_SSE_DELIST_SOURCE_NOT_RETRIEVED_BY_RUNNER",
            "HISTORICAL_PUBLICATION_INSTANT_UNVERIFIED",
            "SOURCE_RAW_BYTES_NOT_ARCHIVED_FOR_REPLAY",
            "FULL_HISTORICAL_ISSUER_STATE_NOT_CERTIFIED",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", default="reports/p3_cninfo_600421_disclosure_pdf_20261021.json")
    ap.add_argument("--asof-day", required=True, choices=DATES)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = normalize_notice(json.loads(Path(args.receipt).read_text("utf-8")),
                              args.asof_day)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
