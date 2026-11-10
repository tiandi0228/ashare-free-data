"""Read-only P2 archived-price evidence to P4 dual-horizon gap reconciliation.

Real archived descriptive observations are not current quotes, investment
recommendations, sector strength, a short entry signal, or a medium thesis.
Locally hashed source excerpts are NOT authenticated independent sources.
"""
import argparse
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from collector.p4_dual_horizon_research import SHORT, MEDIUM, MAINBOARD
from collector.p2_real_archive_research_screen import PHASE as P2_PHASE

SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
SHORT_UNPROVEN = sorted(set(SHORT) | {
    "net_risk_reward_ratio", "planned_net_portfolio_loss_fraction",
    "official_pit_st_halt_verified", "current_quote_and_fill_verified",
    "sector_rotation_verified", "strategy_OOS_validated"})
MEDIUM_UNPROVEN = sorted(set(MEDIUM) | {
    "stress_drawdown_fraction", "debt_and_liquidity_risk_reviewed",
    "earnings_event_risk_reviewed", "fundamental_invalidation_defined",
    "official_pit_st_halt_verified", "current_financial_publication_verified",
    "independent_valuation_verified"})
MAX_ROWS = 128


def _day(value):
    if not isinstance(value, str):
        raise ValueError("missing observation date")
    d = date.fromisoformat(value)
    if d.isoformat() != value:
        raise ValueError("noncanonical observation date")
    return d


def _num(value):
    if not isinstance(value, str):
        raise ValueError("numeric archived observation must be string")
    try:
        d = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid descriptive numeric observation") from None
    if not d.is_finite():
        raise ValueError("nonfinite archived price observation")
    return d


def join(screen, receipt_gate, asof):
    today = _day(asof)
    if (not isinstance(screen, dict)
        or screen.get("phase") != P2_PHASE
        or screen.get("status") != "DESCRIPTIVE_ARCHIVED_SAMPLE_ONLY"
        or screen.get("trade_gate") != "BLOCKED"
        or screen.get("orders") != []
        or screen.get("executable_candidates") != []
        or screen.get("actionable_buy_signals") != []
        or screen.get("historical_PIT_verified") is not False
        or screen.get("historical_OOS_validated") is not False
        or screen.get("complete_mainboard_coverage") is not False
        or not isinstance(screen.get("source_epoch_sha256"), str)
        or not SHA.fullmatch(screen["source_epoch_sha256"])
        or not isinstance(screen.get("archive_commit_sha"), str)
        or not COMMIT.fullmatch(screen["archive_commit_sha"])):
        raise ValueError("untrusted or incomplete archived P2 research screen")
    observed_date = _day(screen.get("asof_completed_day"))
    if observed_date > today:
        raise ValueError("future-dated archived P2 observation")
    ranked = screen.get("descriptive_order")
    if (not isinstance(ranked, list) or len(ranked) > MAX_ROWS
        or type(screen.get("ranked_observations")) is not int
        or len(ranked) != screen["ranked_observations"]
        or type(screen.get("source_gap_count")) is not int
        or type(screen.get("scoped_issuers")) is not int
        or screen["source_gap_count"] < 0
        or len(ranked) + screen["source_gap_count"] != screen["scoped_issuers"]
        or screen["scoped_issuers"] > MAX_ROWS):
        raise ValueError("archived P2 sample counts do not reconcile")
    if (not isinstance(receipt_gate, dict)
        or receipt_gate.get("phase") != "P4_DUAL_HORIZON_RECEIPT_PROVENANCE_GATE"
        or receipt_gate.get("status") !=
            "LOCAL_RECEIPT_INTEGRITY_ONLY_SOURCE_AUTHENTICITY_UNVERIFIED"
        or receipt_gate.get("source_authenticity_verified") is not False
        or receipt_gate.get("semantic_claims_independently_verified") is not False
        or receipt_gate.get("official_pit_universe_certified") is not False
        or receipt_gate.get("buy_recommendations_authorized") is not False
        or receipt_gate.get("trade_gate") != "BLOCKED"
        or receipt_gate.get("orders") != []
        or receipt_gate.get("executable_candidates") != []
        or _day(receipt_gate.get("asof")) != today):
        raise ValueError("untrusted, unmatched, or falsely certified receipt gate")
    underlying = receipt_gate.get("provisional_assertion_only_assessment")
    if (not isinstance(underlying, dict)
        or underlying.get("trade_gate") != "BLOCKED"
        or underlying.get("orders") != []
        or underlying.get("buy_recommendations_authorized") is not False
        or underlying.get("historical_PIT_verified") is not False
        or underlying.get("asof") != asof
        or type(receipt_gate.get("evaluated_symbols")) is not int
        or type(underlying.get("evaluated_symbols")) is not int
        or underlying["evaluated_symbols"] != receipt_gate["evaluated_symbols"]
        or not isinstance(underlying.get("symbols"), list)
        or len(underlying["symbols"]) != receipt_gate["evaluated_symbols"]):
        raise ValueError("receipt gate provisional research not reconciled")
    claims = {}
    for r in underlying["symbols"]:
        if not isinstance(r, dict) or not isinstance(r.get("issuer"), str):
            raise ValueError("invalid receipt gate issuer")
        if r["issuer"] in claims or not MAINBOARD.fullmatch(r["issuer"]):
            raise ValueError("duplicate or nonmainboard receipt issuer")
        claims[r["issuer"]] = r
    result = []
    seen = set()
    for row in ranked:
        if not isinstance(row, dict):
            raise ValueError("malformed descriptive observation")
        code = row.get("issuer")
        if (not isinstance(code, str) or not MAINBOARD.fullmatch(code)
            or code in seen or row.get("buy_signal") is not False
            or row.get("asof_completed_day") != observed_date.isoformat()
            or not isinstance(row.get("source_original_sha256"), str)
            or not SHA.fullmatch(row["source_original_sha256"])
            or type(row.get("above_ma20")) is not bool):
            raise ValueError("unsafe archived P2 issuer observation")
        seen.add(code)
        price = _num(row.get("last_close_cny"))
        volume = _num(row.get("volume_vs_prior20_ratio"))
        drawdown = _num(row.get("drawdown_pct"))
        score = _num(row.get("descriptive_score"))
        if price <= 0 or volume < 0 or not 0 <= drawdown <= 100 or abs(score) > 1000:
            raise ValueError("out-of-bounds archived P2 research features")
        provisional = claims.get(code)
        # A P4 receipt gate with all locally asserted conditions is still not
        # authenticated; especially do NOT claim a B or C buy recommendation.
        result.append({
            "issuer": code,
            "source_original_sha256": row["source_original_sha256"],
            "descriptive_ohlc_completed_day": observed_date.isoformat(),
            "archived_above_ma20": row["above_ma20"],
            "archived_volume_ratio_vs_20": str(volume),
            "archived_descriptive_score": str(score),
            "archived_observation_age_days": (today - observed_date).days,
            "archived_quote_is_current": False,
            "sector_leadership_from_archived_sample_proven": False,
            "short_horizon": {
                "state": "EVIDENCE_INCOMPLETE_NOT_ACTIONABLE",
                "required_independent_proofs": SHORT_UNPROVEN,
                "provisional_receipt_state": (
                    provisional["short"]["state"] if provisional else None)},
            "medium_horizon": {
                "state": "EVIDENCE_INCOMPLETE_NOT_ACTIONABLE",
                "required_independent_proofs": MEDIUM_UNPROVEN,
                "provisional_receipt_state": (
                    provisional["medium"]["state"] if provisional else None)},
            "category": "D_NO_VERIFIED_BUY_THESIS",
        })
    return {
        "phase": "P4_ARCHIVED_P2_TO_DUAL_HORIZON_EVIDENCE_GAP_JOIN",
        "status": "ARCHIVED_DESCRIPTIVE_EVIDENCE_NOT_ACTIONABLE",
        "asof": asof, "archive_p2_completed_day": observed_date.isoformat(),
        "archive_commit_sha": screen["archive_commit_sha"],
        "archive_epoch_sha256": screen["source_epoch_sha256"],
        "p2_scoped_issuer_count": screen["scoped_issuers"],
        "p2_descriptive_rows": len(result),
        "p2_missing_feature_issuer_count": screen["source_gap_count"],
        "p4_receipt_issuer_count": len(claims),
        "p4_unmatched_receipt_issuers": sorted(set(claims) - seen),
        "symbols": result,
        "all_market_coverage_verified": False,
        "archived_price_observations_not_live": True,
        "finance_valuation_and_sector_not_inferred": True,
        "official_pit_verified": False,
        "source_claims_authenticated": False,
        "buy_recommendations_authorized": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--p2-screen", type=Path, required=True)
    parser.add_argument("--receipt-gate", type=Path, required=True)
    parser.add_argument("--asof", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    joined = join(json.loads(args.p2_screen.read_text()),
                  json.loads(args.receipt_gate.read_text()), args.asof)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(joined, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": joined["phase"],
                      "p2_descriptive_rows": joined["p2_descriptive_rows"],
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
