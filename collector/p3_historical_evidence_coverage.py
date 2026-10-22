"""P3 evidence-coverage gate for a bounded historical issuer universe.

A vendor bar or undated web link never proves historical ST, halt or delist
status. Missing issuer/date/event evidence fails closed. Offline only.
"""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
import re

CODE = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")

def verified_before_decision(observation):
    # Decision dates follow Shanghai/Shenzhen exchange time (UTC+08), not UTC.
    raw = observation.get('publication_instant_utc')
    if not isinstance(raw, str) or not raw.endswith('Z'):
        return False
    try:
        instant = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        day = date.fromisoformat(observation['decision_date'])
        published_day = date.fromisoformat(observation['publication_day'])
        return (instant.tzinfo is not None and
                instant.astimezone(timezone.utc).date() == published_day and
                instant.astimezone(timezone(timedelta(hours=8))).date() < day)
    except (ValueError, TypeError, KeyError):
        return False

KINDS = ("listing", "st", "halt", "delisting")

def audit_coverage(codes, days, observations):
    if not isinstance(codes, list) or not codes or any(not isinstance(x, str) for x in codes) or len(codes) != len(set(codes)):
        raise ValueError("invalid frozen issuer pool")
    if not isinstance(days, list) or not days or any(not isinstance(x, str) for x in days) or len(days) != len(set(days)):
        raise ValueError("invalid frozen decision dates")
    if any(not isinstance(c, str) or not CODE.fullmatch(c) for c in codes):
        raise ValueError("invalid issuer id")
    try:
        for d in days:
            if not isinstance(d, str) or date.fromisoformat(d).isoformat() != d:
                raise ValueError("invalid day")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid decision date") from exc
    if len(codes) > 100 or len(days) > 31:\n        raise ValueError("bounded P3 audit scope exceeded")\n    if not isinstance(observations, list):
        raise ValueError("invalid evidence")
    expected = {(c, d, k) for c in codes for d in days for k in KINDS}
    verified = set()
    seen = set()
    rejected = 0
    for o in observations:
        if not isinstance(o, dict):
            raise ValueError("invalid observation")
        key = (o.get("code"), o.get("decision_date"), o.get("kind"))
        if key not in expected:
            raise ValueError("evidence outside frozen scope")
        if key in seen:
            raise ValueError("duplicate evidence for issuer/date/kind")
        seen.add(key)
        # Require a source original, authenticated timestamp <= decision day,
        # and contemporaneous official exchange provenance. Hash alone is
        # insufficient; third-party retrospective rows cannot pass.
        valid = (o.get("original_bytes_verified") is True
                 and o.get("official_exchange_source_verified") is True
                 and o.get("publication_instant_verified") is True
                 and o.get("historical_asof_verified") is True
                 and o.get("entire_decision_day_state_covered") is True
                 and isinstance(o.get("original_sha256"), str)
                 and len(o["original_sha256"]) == 64
                 and all(ch in "0123456789abcdef" for ch in o["original_sha256"])
                 and isinstance(o.get("publication_day"), str)
                 and verified_before_decision(o))
        if valid:
            verified.add(key)
        else:
            rejected += 1
    missing = sorted(expected - verified)
    return {
        "phase": "P3_OFFICIAL_HISTORICAL_EVENT_COVERAGE",
        "required_evidence_cells": len(expected),
        "verified_evidence_cells": len(verified),
        "rejected_evidence_records": rejected,
        "missing_evidence_cells": len(missing),
        "sample_missing_cells": [list(k) for k in missing[:12]],
        "self_reported_cell_claims_complete": len(missing) == 0,
        "independent_source_authentication_performed": False,
        "complete": False,  # no independent original/timestamp proof in this offline function
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
        "paid_api_calls": 0,
        "note": "Input boolean flags and hashes are self-reported; this offline function cannot independently authenticate source bytes or historical timestamps. Structural cell counts cannot certify historical coverage.",
    }
