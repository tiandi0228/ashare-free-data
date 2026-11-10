"""Aggregate immutable-looking *claims* about frozen event forecasts, research only.

This report never promotes minute-compatible shapes to certified wins or uses
the number of resolved-looking submissions as a return/accuracy denominator.
A SHA string alone does not authenticate independent third-party provenance.
"""
import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from collector.p4_dual_horizon_research import MAINBOARD
from collector.p4_oneword_prediction_replay import RULE

PHASE = "P4_EVENT_FORECAST_COHORT_RESEARCH_ONLY"
SHA = re.compile(r"[a-f0-9]{64}\Z")
ALLOWED = {
    "UNRESOLVED_NO_INDEPENDENT_SESSION_EVIDENCE",
    "UNRESOLVED_PARTIAL_SESSION_OBSERVATION",
    "DAILY_OHLC_COMPATIBLE_NOT_CERTIFIED_ONE_WORD",
    "FALSIFIED_BY_DAILY_COMPLETED_OHLC_CLAIM",
    "MINUTE_BARS_COMPATIBLE_ONE_WORD_NOT_CERTIFIED",
    "CONTRADICTED_BY_LOCALLY_REPLAYED_MINUTE_LOW",
}
CONTRADICTIONS = {
    "FALSIFIED_BY_DAILY_COMPLETED_OHLC_CLAIM",
    "CONTRADICTED_BY_LOCALLY_REPLAYED_MINUTE_LOW",
}
COMPATIBLE = {
    "DAILY_OHLC_COMPATIBLE_NOT_CERTIFIED_ONE_WORD",
    "MINUTE_BARS_COMPATIBLE_ONE_WORD_NOT_CERTIFIED",
}


def _date(value):
    if not isinstance(value, str):
        raise ValueError("date required")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("noncanonical date")
    return parsed


def assess(packet):
    if not isinstance(packet, dict) or type(packet.get("forecasts")) is not list:
        raise ValueError("forecast cohort packet required")
    asof = _date(packet.get("asof"))
    entries = packet["forecasts"]
    if len(entries) > 500:
        raise ValueError("cohort scope exceeded")
    seen = set()
    distribution = Counter()
    pending = contradicted = compatible = 0
    results = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("malformed forecast entry")
        code = entry.get("issuer")
        if not isinstance(code, str) or not MAINBOARD.fullmatch(code):
            raise ValueError("invalid short mainboard issuer")
        predicted = _date(entry.get("predicted_on"))
        session = _date(entry.get("session_on"))
        if not predicted < session:
            raise ValueError("prediction must precede target")
        if predicted > asof:
            raise ValueError("cannot have future-dated recorded prediction")
        if entry.get("prediction") != "ONE_WORD_LIMIT_UP" or entry.get("prediction_rule") != RULE:
            raise ValueError("nonfrozen prediction taxonomy")
        if entry.get("trade_gate") != "BLOCKED" or entry.get("orders") != []:
            raise ValueError("forecast with executable order rejected")
        prediction_sha = entry.get("prediction_sha256")
        if not isinstance(prediction_sha, str) or not SHA.fullmatch(prediction_sha):
            raise ValueError("forecast provenance digest missing")
        identity = (code, session.isoformat(), entry["prediction"])
        if identity in seen:
            raise ValueError("duplicated issuer and target prediction")
        seen.add(identity)
        state = entry.get("audit_state")
        if state not in ALLOWED:
            raise ValueError("unknown replay audit state")
        source_sha = entry.get("observation_sha256")
        if state == "UNRESOLVED_NO_INDEPENDENT_SESSION_EVIDENCE":
            if source_sha is not None:
                raise ValueError("unobserved forecast cannot claim an observation digest")
        else:
            if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
                raise ValueError("replay evidence digest required")
            if session > asof:
                raise ValueError("cannot use future-session observation")
        if type(entry.get("independent_external_source_authenticated")) is not bool:
            raise ValueError("explicit source authentication status required")
        if entry["independent_external_source_authenticated"]:
            raise ValueError("self-asserted source authentication is not independently verified")
        if type(entry.get("prediction_pre_event_timestamp_authenticated")) is not bool:
            raise ValueError("explicit forecast time authentication status required")
        if entry["prediction_pre_event_timestamp_authenticated"]:
            raise ValueError("self-asserted pre-event timestamp is not independently verified")
        distribution[state] += 1
        if state in CONTRADICTIONS:
            contradicted += 1
            klass = "CONTRADICTS_ONE_WORD_SHAPE_NOT_INDEPENDENTLY_AUTHENTICATED"
        elif state in COMPATIBLE:
            compatible += 1
            klass = "COMPATIBLE_ONLY_NEVER_A_CERTIFIED_HIT"
        else:
            pending += 1
            klass = "UNRESOLVED"
        results.append({"issuer": code, "predicted_on": predicted.isoformat(),
                        "session_on": session.isoformat(),
                        "classification": klass, "audit_state": state,
                        "observation_source_sha256": source_sha})
    return {
        "phase": PHASE, "asof": asof.isoformat(),
        "submitted_forecasts": len(entries),
        "unresolved": pending,
        "locally_contradicted_unverified": contradicted,
        "locally_compatible_unverified": compatible,
        "state_counts": {s: distribution[s] for s in sorted(ALLOWED)},
        "forecasts": results,
        "verified_successes": 0,
        "independently_verified_forecast_sample_size": 0,
        "hit_rate": None, "risk_adjusted_return": None,
        "full_market_screen_performed": False,
        "external_source_provenance_replayed": False,
        "immutable_pre_event_forecasts_authenticated": False,
        "cannot_promote_compatible_to_win": True,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = assess(json.loads(a.packet.read_text(encoding="utf-8")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": PHASE, "submitted_forecasts": result["submitted_forecasts"],
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
