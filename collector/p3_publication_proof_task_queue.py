"""Deterministic read-only P3 research tasks from a publication-as-of gap report.

This queue cannot infer historical issuer state or authorize trades. Every task
needs independent evidence; no absence-of-notice proof is asserted.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

PHASE = "P3_PUBLICATION_PROOF_GAP_TASK_QUEUE"
SOURCE_PHASE = "P3_EVENT_PUBLICATION_ASOF_BOUNDARY"
SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")
ACTION = {
    "ORIGINAL_BYTES_NOT_VERIFIED": (1, "ACQUIRE_AND_SHA_VERIFY_OFFICIAL_ORIGINAL"),
    "PUBLISHER_NOT_AUTHENTICATED": (2, "VALIDATE_OFFICIAL_PUBLISHER_ORIGIN"),
    "FIRST_PUBLICATION_NOT_AUTHENTICATED": (3, "AUTHENTICATE_OFFICIAL_FIRST_PUBLICATION_INSTANT"),
    "PUBLICATION_AFTER_DECISION": (4, "REJECT_LOOKAHEAD_AND_REVIEW_PRIOR_SOURCE"),
    "EFFECTIVE_DATE_AFTER_DECISION": (5, "RETAIN_PENDING_EFFECTIVE_DATE_RESEARCH"),
    "EVENT_KNOWN_FULL_DAILY_STATE_UNCERTIFIED": (6, "RECONCILE_FULL_OFFICIAL_ISSUER_DAY_STATE"),
}


def build(report):
    if (not isinstance(report, dict)
        or report.get("phase") != SOURCE_PHASE
        or report.get("trade_gate") != "BLOCKED"
        or report.get("orders") != []
        or report.get("executable_candidates") != []
        or report.get("eligible_for_trading") is not False
        or report.get("complete_historical_risk_state") is not False):
        raise ValueError("unsafe or unexpected P3 as-of source")
    events = report.get("events")
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("invalid P3 events inventory")
    counts = Counter()
    tasks = []
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("invalid P3 event")
        issuer = event.get("issuer")
        digest = event.get("original_sha256")
        kind = event.get("kind")
        status = event.get("publication_proof_status")
        if (not isinstance(issuer, str) or not ISSUER.fullmatch(issuer)
            or not isinstance(digest, str) or not SHA.fullmatch(digest)
            or not isinstance(kind, str) or not kind or len(kind) > 80
            or status not in ACTION
            or event.get("certified_full_daily_state") is not False
            or type(event.get("known_before_decision")) is not bool
            or type(event.get("effective_by_decision_date")) is not bool):
            raise ValueError("untrusted or promoted P3 event")
        day = event.get("effective_date")
        if not isinstance(day,str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",day):
            raise ValueError("missing candidate event day")
        key = issuer, kind, digest, day
        if key in seen:
            raise ValueError("duplicate P3 event identity")
        seen.add(key)
        # Status must not falsely claim missing proof while reporting proof
        # that could only exist after authentication.
        if status == "EVENT_KNOWN_FULL_DAILY_STATE_UNCERTIFIED":
            if not event["known_before_decision"] or not event["effective_by_decision_date"]:
                raise ValueError("contradictory known event")
        elif status in ("ORIGINAL_BYTES_NOT_VERIFIED", "PUBLISHER_NOT_AUTHENTICATED",
                        "FIRST_PUBLICATION_NOT_AUTHENTICATED", "PUBLICATION_AFTER_DECISION"):
            if event["known_before_decision"] or event["effective_by_decision_date"]:
                raise ValueError("look-ahead or contradictory event")
        elif status == "EFFECTIVE_DATE_AFTER_DECISION":
            if not event["known_before_decision"] or event["effective_by_decision_date"]:
                raise ValueError("contradictory pending event")
        priority, action = ACTION[status]
        counts[status] += 1
        tasks.append({
            "priority": priority, "issuer": issuer, "kind": kind,
            "original_sha256": digest, "candidate_text_day_unverified": day,
            "missing_proof": status,
            "research_action": action,
            "historical_PIT_verified": False, "trade_eligible": False,
        })
    expected = report.get("publication_proof_status_counts")
    if (not isinstance(expected, dict) or expected != dict(sorted(counts.items()))
        or type(report.get("known_event_count")) is not int
        or report["known_event_count"] != sum(
            bool(row["known_before_decision"]) for row in events)):
        raise ValueError("P3 counts do not reconcile")
    tasks.sort(key=lambda x: (x["priority"], x["issuer"], x["kind"], x["original_sha256"], x["candidate_text_day_unverified"]))
    return {
        "phase": PHASE, "status": "OFFICIAL_PROOF_RESEARCH_TASKS_ONLY",
        "source_phase": SOURCE_PHASE,
        "source_decision_instant_utc": report.get("decision_instant_utc"),
        "task_count": len(tasks), "task_counts_by_missing_proof": dict(sorted(counts.items())),
        "tasks": tasks, "historical_PIT_verified": False,
        "full_market_historical_state_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof-report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = build(json.loads(args.asof_report.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
