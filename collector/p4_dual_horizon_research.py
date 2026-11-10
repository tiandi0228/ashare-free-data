"""Independent A-share short (3-5 sessions) and medium (1-3 months) research.

Inputs must be timestamped evidence, not assumptions or model-generated price
claims. No lane can rescue the other lane's failed checks. This produces an
offline research suitability taxonomy, NOT actionable signals or orders.
"""
import argparse
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

PHASE = "P4_DUAL_HORIZON_INDEPENDENT_RESEARCH_SCREEN"
MAINBOARD = re.compile(r"(?:sh\\.(?:600|601|603|605)|sz\\.(?:000|001|002|003))[0-9]{3}\Z")
HORIZONS = {"short": "3_TO_5_TRADING_SESSIONS",
            "medium": "1_TO_3_CALENDAR_MONTHS"}
SHORT = ("price_structure_confirmed", "relative_strength_confirmed",
         "sector_leadership_confirmed", "volume_expansion_confirmed",
         "fresh_material_catalyst_verified")
MEDIUM = ("fundamental_improvement_confirmed", "valuation_margin_confirmed",
          "medium_catalyst_confirmed", "financial_health_reviewed",
          "sector_cycle_confirmed")
EXECUTION = ("fresh_executable_quotes", "historical_point_in_time_certified",
             "official_disclosure_and_st_verified", "exchange_calendar_verified",
             "fee_risk_and_t_plus_one_verified", "fills_verified")
RESEARCH_STATES = ("RESEARCH_FIT_NOT_ACTIONABLE", "EVIDENCE_INCOMPLETE",
                   "RESEARCH_RISK_REJECTED")


def _day(value):
    if not isinstance(value, str):
        raise ValueError("evidence date required")
    day = date.fromisoformat(value)
    if day.isoformat() != value:
        raise ValueError("noncanonical evidence day")
    return day


def _bool(value):
    if type(value) is not bool:
        raise ValueError("explicit boolean evidence flag required")
    return value


def _risk_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("risk ratio must be finite decimal")
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid decimal risk ratio") from None
    if not num.is_finite() or num < 0:
        raise ValueError("risk ratio cannot be negative or nonfinite")
    return num


def _lane(data, asof, horizon):
    checks = SHORT if horizon == "short" else MEDIUM
    if not isinstance(data, dict):
        return {"horizon": HORIZONS[horizon], "state": "EVIDENCE_INCOMPLETE",
                "reasons": ["NO_INDEPENDENT_LANE_EVIDENCE"],
                "trade_gate": "BLOCKED", "buy_recommendations_authorized": False}
    issues = []
    failed = []
    source = data.get("source")
    observed = data.get("published_on")
    if not isinstance(source, str) or not source.strip() or len(source) > 512:
        issues.append("EVIDENCE_SOURCE_NOT_PINNED")
    try:
        published = _day(observed)
        if published > asof:
            issues.append("FUTURE_DATED_EVIDENCE_REJECTED")
    except (ValueError, TypeError):
        issues.append("INVALID_PUBLICATION_DAY")
    for check in checks:
        try:
            value = _bool(data[check])
        except (KeyError, ValueError):
            issues.append("MISSING_OR_INVALID_" + check.upper())
            continue
        if not value:
            failed.append(check.upper() + "_NOT_CONFIRMED")
    if horizon == "short":
        try:
            net_rr = _risk_number(data["net_risk_reward_ratio"])
            risk = _risk_number(data["planned_net_portfolio_loss_fraction"])
            if net_rr < Decimal("2"):
                failed.append("NET_RISK_REWARD_BELOW_2_TO_1")
            if risk > Decimal("0.03"):
                failed.append("PLANNED_NET_PORTFOLIO_RISK_EXCEEDS_3_PERCENT")
        except (KeyError, ValueError):
            issues.append("SHORT_RISK_MATH_NOT_VERIFIED")
    else:
        try:
            drawdown = _risk_number(data["stress_drawdown_fraction"])
            if drawdown > Decimal("1"):
                issues.append("MEDIUM_DRAWDOWN_FRACTION_INVALID")
        except (KeyError, ValueError):
            issues.append("MEDIUM_STRESS_DRAWDOWN_NOT_QUANTIFIED")
        for flag in ("debt_and_liquidity_risk_reviewed",
                     "earnings_event_risk_reviewed",
                     "fundamental_invalidation_defined"):
            try:
                if not _bool(data[flag]):
                    failed.append(flag.upper() + "_NOT_CONFIRMED")
            except (KeyError, ValueError):
                issues.append("MISSING_OR_INVALID_" + flag.upper())
    # This is NEVER an execution gate, even if the research evidence is clean.
    for key in EXECUTION:
        if data.get(key) is True:
            issues.append("EXECUTION_PROOF_NOT_ADMISSIBLE_IN_RESEARCH_MODULE")
    state = ("EVIDENCE_INCOMPLETE" if issues else
             "RESEARCH_RISK_REJECTED" if failed else
             "RESEARCH_FIT_NOT_ACTIONABLE")
    return {"horizon": HORIZONS[horizon], "state": state,
            "reasons": sorted(issues + failed),
            "trade_gate": "BLOCKED",
            "buy_recommendations_authorized": False}


def assess(payload):
    if not isinstance(payload, dict) or type(payload.get("symbols")) is not list:
        raise ValueError("read-only symbol research list required")
    records = payload["symbols"]
    if len(records) > 50:
        raise ValueError("bounded research symbol list exceeded")
    asof = _day(payload.get("asof"))
    seen = set()
    results = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("malformed research symbol")
        code = record.get("issuer")
        if not isinstance(code, str) or code in seen:
            raise ValueError("invalid or duplicated research issuer")
        seen.add(code)
        if not MAINBOARD.fullmatch(code):
            results.append({"issuer": code, "category": "D_REJECTED",
                            "short": {"state": "RESEARCH_RISK_REJECTED",
                                      "reasons": ["OUTSIDE_SHANGHAI_SHENZHEN_MAINBOARD"]},
                            "medium": {"state": "RESEARCH_RISK_REJECTED",
                                       "reasons": ["OUTSIDE_SHANGHAI_SHENZHEN_MAINBOARD"]}})
            continue
        # ST or suspended is a point-in-time matter. An explicit check is
        # mandatory; lack of source is NOT interpreted as clean eligibility.
        guard = record.get("universe_guard")
        eligible = (isinstance(guard, dict) and
                    guard.get("official_pit_mainboard_non_st_confirmed") is True and
                    guard.get("no_suspension_confirmed") is True and
                    isinstance(guard.get("source"), str) and bool(guard["source"].strip()))
        if eligible:
            try:
                eligible = _day(guard.get("published_on")) <= asof
            except (ValueError, TypeError):
                eligible = False
        short = _lane(record.get("short"), asof, "short")
        medium = _lane(record.get("medium"), asof, "medium")
        if not eligible:
            for lane in (short, medium):
                lane["state"] = "EVIDENCE_INCOMPLETE"
                lane["reasons"] = sorted(set(lane["reasons"] +
                                              ["OFFICIAL_POINT_IN_TIME_UNIVERSE_GUARD_MISSING"]))
        s = short["state"] == "RESEARCH_FIT_NOT_ACTIONABLE"
        m = medium["state"] == "RESEARCH_FIT_NOT_ACTIONABLE"
        category = ("C_DUAL_HORIZON_RESEARCH_ONLY" if s and m else
                    "A_SHORT_RESEARCH_ONLY" if s else
                    "B_MEDIUM_RESEARCH_ONLY" if m else
                    "D_NO_VERIFIED_RESEARCH_FIT")
        results.append({"issuer": code, "category": category,
                        "short": short, "medium": medium})
    return {"phase": PHASE, "asof": asof.isoformat(),
            "horizons": HORIZONS,
            "categories_are_not_buy_recommendations": True,
            "short_cannot_fallback_to_medium": True,
            "medium_requires_independent_fundamental_evidence": True,
            "evaluated_symbols": len(results),
            "symbols": results,
            "trade_gate": "BLOCKED",
            "orders": [], "executable_candidates": [],
            "buy_recommendations_authorized": False,
            "historical_PIT_verified": False,
            "realtime_execution_verified": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = assess(json.loads(args.evidence.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"phase": PHASE, "evaluated_symbols": result["evaluated_symbols"],
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
