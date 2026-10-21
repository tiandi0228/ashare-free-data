"""Fail-closed historical PIT acceptance based on real public *digest receipts*.

This is a quality gate, not a listing reconstruction or an alpha strategy.
Real original bytes are NOT stored in these receipt JSONs. All sources under
test remain unfit for historical trade simulation until P3/P4 independently pass.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
import re

SHA = re.compile(r"[0-9a-f]{64}\Z")
CODE = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
ALLOWED_SNAPSHOTS = ("2025-05-26", "2026-10-20")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(ok, explanation):
    if not ok:
        raise ValueError(explanation)


def audit_and_block(lifecycle_metadata, source_digest_metadata, decision_date):
    historical_day = date.fromisoformat(decision_date)
    require(decision_date in ALLOWED_SNAPSHOTS,
            "No vendor snapshot estimate for requested day")

    lifecycle = lifecycle_metadata
    r = lifecycle.get("source_report", {})
    require(lifecycle.get("audit_type") == "FREE_VENDOR_RETROSPECTIVE_LIFECYCLE_METADATA_ONLY",
            "Lifecycle source audit type changed")
    require(lifecycle.get("public_workflow_result") == "success"
            and lifecycle.get("public_run_id") == 39576085424,
            "Expected successful source run not linked")
    require(SHA.fullmatch(lifecycle.get("source_original_csv_sha256", "")) is not None
            and lifecycle["source_original_csv_sha256"] == r.get("source_csv_sha256"),
            "Unreconciled vendor source digest receipt")
    require(r.get("original_source_rows") == 9018
            and r.get("mainboard_prefix_lifecycles") == 3489
            and r.get("vendor_currently_delisted_mainboard_rows") == 294,
            "Frozen research lifecycle receipt changed")
    require(r.get("logical_query_attempts") == 1 and r.get("paid_api_calls") == 0,
            "Bounded source request invariant failed")
    require(r.get("historical_point_in_time_universe_verified") is False
            and r.get("source_exchange_authenticated") is False,
            "Vendor data falsely marked official PIT certified")
    require(r.get("trade_gate") == "BLOCKED"
            and r.get("orders") == [] and r.get("executable_candidates") == [],
            "Vendor upstream trade gate was changed")
    estimates = r.get("retrospective_interval_candidates", [])
    require([x.get("date") for x in estimates] == list(ALLOWED_SNAPSHOTS),
            "Historical estimate dates changed")
    for x in estimates:
        require(x.get("source_datetime_proves_historical_knowledge") is False
                and x.get("verified_historical_ST_halt_state") is False,
                "Retrospective estimate mislabeled as historical observable state")
        require(isinstance(x.get("candidate_issuer_count_from_vendor_dates"), int)
                and x["candidate_issuer_count_from_vendor_dates"] > 1000,
                "Implausible research-only pool count")
    selected = next(x for x in estimates if x["date"] == decision_date)

    meta = source_digest_metadata
    audit = meta.get("audit_report", {})
    require(meta.get("evidence_type") == "SOURCE_SHA_METADATA_ONLY_NO_CSV_REDISTRIBUTION",
            "16 issuer source digests must be labeled as non-reconstructible")
    require(meta.get("capture_run_ids") == [39572697952, 39573265839]
            and audit.get("source_run_ids") == meta["capture_run_ids"],
            "Two original runs mismatch")
    require(audit.get("status") == "OBSERVED_16_CURRENT_ISSUERS_RESEARCH_ONLY"
            and audit.get("issuer_count") == 16
            and audit.get("original_source_rows") == 7760
            and audit.get("trade_status_1_rows") == 7750
            and audit.get("trade_status_0_rows") == 10,
            "Source-bar audit receipt inconsistency")
    require(audit.get("market_wide_backfill_complete") is False
            and audit.get("historical_point_in_time_universe_verified") is False
            and audit.get("backtest_or_live_signal_validated") is False,
            "Research subset falsely marked production-ready")
    require(audit.get("trade_gate") == "BLOCKED"
            and audit.get("orders") == [] and audit.get("executable_candidates") == [],
            "Original 16-issuer audit no-trade invariant changed")
    receipts = audit.get("issuers", [])
    require(len(receipts) == 16, "Missing issuer digest entry")
    codes = [entry.get("code") for entry in receipts]
    require(len(set(codes)) == 16
            and all(isinstance(code, str) and CODE.fullmatch(code) for code in codes),
            "Invalid mainboard source subset identity")
    require(all(isinstance(entry.get("source_sha256"), str)
                and SHA.fullmatch(entry["source_sha256"]) for entry in receipts),
            "Missing SHA-256 original-source digest")
    require(sum(entry.get("source_rows", -1) for entry in receipts) == 7760
            and sum(entry.get("tradable_status_rows", -1) for entry in receipts) == 7750
            and sum(entry.get("suspended_status_rows", -1) for entry in receipts) == 10,
            "Original issuer row accounting changed")
    require(audit.get("paid_api_calls") == 0, "Provider calls no longer zero-cost")
    same_scope = lifecycle.get("same_scope_membership_equality_verified")
    require(same_scope is False,
            "One provider's retrospective pool cannot certify private baseline scope")
    require(lifecycle.get("simple_numerical_difference_not_scope_validated") == 143,
            "Frozen baseline difference receipt changed")
    require(lifecycle.get("private_2026_10_20_mainboard_baseline_count") == 3052,
            "Baseline comparison unexpectedly changed")

    # These are quarantined for *all* historical decision dates because
    # provider lifecycle dates reflect information reconstructed after the fact.
    return {
        "phase": "P1_P3_HISTORICAL_POINT_IN_TIME_ACCEPTANCE",
        "status": "BLOCKED_NO_CERTIFIED_HISTORICAL_UNIVERSE",
        "decision_date": historical_day.isoformat(),
        "vendor_retrospective_candidate_count": selected["candidate_issuer_count_from_vendor_dates"],
        "vendor_later_delisted_count": selected["vendor_currently_delisted_but_candidate_at_date"],
        "recovered_source_receipts": 16,
        "original_source_bytes_available_in_metadata": False,
        "original_source_reverified_in_this_run": False,
        "trusted_historical_as_of_publication": False,
        "same_scope_universe_comparison_verified": False,
        "exchange_official_membership_complete": False,
        "historical_ST_halt_delist_complete": False,
        "candidate_universe": [],
        "executable_candidates": [],
        "orders": [],
        "trade_gate": "BLOCKED",
        "p4_out_of_sample_certified": False,
        "paid_api_calls": 0,
        "blockers": [
            "RETROSPECTIVE_VENDOR_DATES_NOT_CONTEMPORANEOUSLY_CAPTURED",
            "HISTORICAL_ST_HALT_DELIST_EVENTS_INCOMPLETE",
            "EXCHANGE_LISTING_MEMBERSHIP_UNCERTIFIED",
            "INDEPENDENT_SOURCE_POOL_SCOPES_NOT_RECONCILED",
            "ONLY_SHA_RECEIPTS_NOT_RECONSTRUCTIBLE_ORIGINAL_BYTES",
            "P4_RESEARCH_VALIDATION_NOT_COMPLETED",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lifecycle", default="reports/p1_vendor_lifecycle_20261021.json")
    p.add_argument("--source-digests", default="reports/p1_pilot_16_source_digests_20261021.json")
    p.add_argument("--decision-date", required=True, choices=ALLOWED_SNAPSHOTS)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    try:
        result = audit_and_block(read_json(args.lifecycle), read_json(args.source_digests),
                                 args.decision_date)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise SystemExit("FAIL CLOSED: " + type(exc).__name__) from exc
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
