"""Free-source routing for RESEARCH ONLY, using immutable observed receipts.

A functioning public feed must NEVER be promoted into authenticated SSE/SZSE
daily product-status membership. NO paid providers, no trading or recommendations.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

HIST_RUNS = (39572697952, 39573265839)
ISSUER_RUN = 39576085424
PDF_RUNS = (39580585146, 39579302851)
EARLY_SHA = "ef9b9113b2a51ca718e786de0613860351f0c8056916e7decb5a010da7acaff8"
LATER_SHA = "6e43f458ee70b11dc5ab7331c2d67dee62dc26fa2121e138a2c93ef71c65409f"

def required(test, reason):
    if not test:
        raise ValueError(reason)

def evaluate(history, listing, early, late):
    bars = history.get("audit_report", {})
    universe = listing.get("source_report", {})
    a, b = early.get("source_observation", {}), late.get("original_pdf_report", {})
    required(history.get("capture_run_ids") == list(HIST_RUNS)
             and bars.get("source_run_ids") == list(HIST_RUNS)
             and bars.get("issuer_count") == 16
             and bars.get("original_source_rows") == 7760
             and bars.get("trade_status_0_rows") == 10
             and bars.get("historical_point_in_time_universe_verified") is False
             and bars.get("market_wide_backfill_complete") is False
             and bars.get("trade_gate") == "BLOCKED" and bars.get("orders") == [],
             "Market-history research-only receipt invalid")
    required(listing.get("public_run_id") == ISSUER_RUN
             and listing.get("public_workflow_result") == "success"
             and listing.get("same_scope_membership_equality_verified") is False
             and universe.get("mainboard_prefix_lifecycles") == 3489
             and universe.get("historical_point_in_time_universe_verified") is False
             and universe.get("source_exchange_authenticated") is False
             and universe.get("trade_gate") == "BLOCKED" and universe.get("orders") == [],
             "Retrospective issuer lifecycle receipt invalid")
    required((early.get("acquisition_run_id"), late.get("acquisition_run_id")) == PDF_RUNS
             and early.get("conclusion") == "success"
             and late.get("acquisition_conclusion") == "success"
             and a.get("source_sha256") == EARLY_SHA
             and b.get("source_sha256") == LATER_SHA
             and a.get("source_issuer") == "sh.600421"
             and b.get("issuer") == "sh.600421"
             and a.get("trade_gate") == "BLOCKED"
             and b.get("trade_gate") == "BLOCKED"
             and a.get("orders") == [] and b.get("orders") == []
             and a.get("historical_asof_certified") is False
             and b.get("historical_asof_publication_timestamp_verified") is False
             and late.get("sse_original_sha_not_obtained") is True,
             "Issuer disclosure source identity or coverage invalid")
    return {
        "phase": "FREE_SOURCE_FALLBACK_CAPABILITY_ROUTING",
        "status": "RESEARCH_ONLY_NO_AUTHENTICATED_EXCHANGE_STATUS",
        "source_routes": [
            {"purpose": "historical_daily_prices",
             "selected_free_source": "Baostock",
             "verified_scope": "16 fixed issuers, 2 historical years, SHA-only receipts",
             "frozen_source_run_ids": list(HIST_RUNS),
             "can_support_limited_research": True,
             "suitable_for_formal_P3_status": False,
             "whole_market_verified": False},
            {"purpose": "listing_ipo_delist_candidates",
             "selected_free_source": "Baostock query_stock_basic",
             "verified_scope": "retrospective 3489 mainboard-prefix lifecycle records",
             "frozen_source_run_ids": [ISSUER_RUN],
             "can_support_limited_research": True,
             "suitable_for_formal_P3_status": False,
             "point_in_time_authenticated": False},
            {"purpose": "issuer_positive_risk_notices",
             "selected_free_source": "CNINFO static issuer PDF",
             "verified_scope": "2 SHA-anchored PDFs for 1 issuer",
             "frozen_source_run_ids": list(PDF_RUNS),
             "can_support_limited_research": True,
             "suitable_for_formal_P3_status": False,
             "empty_search_proves_no_risk": False},
            {"purpose": "SSE_and_SZSE_historical_full_market_ST_halt_delist",
             "selected_free_source": None,
             "selection_state": "NO_FREE_AUTHENTICATED_COMPLETE_SOURCE_VERIFIED",
             "can_support_limited_research": False,
             "suitable_for_formal_P3_status": False,
             "independent_authorized_delivery_required": True},
        ],
        "source_substitution_policy": {
            "on_network_or_budget_failure": "SWITCH_ONLY_TO_VETTED_FREE_SOURCE_FOR_SAME_RESEARCH_CAPABILITY",
            "cannot_substitute_vendor_or_issuer_notice_for": [
                "exchange_authenticated_complete_ST_halt_delist_membership",
                "historical_asof_source_observation_timestamp",
                "original_byte_replay_licensing",
                "strategy_OOS_trade_execution_approval",
            ],
            "automatic_paid_fallback": False,
            "repeat_failed_probe_without_budget": False,
        },
        "original_source_bytes_reverified_here": False,
        "all_source_original_bytes_durably_archived": False,
        "historical_point_in_time_universe_verified": False,
        "v2_2_validated": False,
        "trade_gate": "BLOCKED",
        "candidate_universe": [],
        "executable_candidates": [],
        "orders": [],
        "paid_api_calls": 0,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--history", default="reports/p1_pilot_16_source_digests_20261021.json")
    p.add_argument("--listing", default="reports/p1_vendor_lifecycle_20261021.json")
    p.add_argument("--early", default="reports/p3_cninfo_600421_early_20261021.json")
    p.add_argument("--later", default="reports/p3_cninfo_600421_disclosure_pdf_20261021.json")
    p.add_argument("--out", required=True)
    args=p.parse_args()
    def read(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    result=evaluate(read(args.history),read(args.listing),read(args.early),read(args.later))
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))

if __name__ == "__main__":
    main()
