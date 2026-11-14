"""Verify a preregistered research protocol without certifying time or returns."""
import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from collector.p4_prospective_protocol_freeze import freeze

BEIJING = timezone(timedelta(hours=8))
EVIDENCE_STATUS = "VENDOR_REPLAY_NOT_CERTIFIED_OOS"
POLICY = {
    "universe": "FIXED_ARCHIVE_EPOCH_COHORT_NOT_PIT_MAINBOARD",
    "window_days": "BEIJING_DATES_INCLUSIVE",
    "signal_input": "COMPLETED_UNADJUSTED_VENDOR_DAILY_CLOSE_PREFIX",
    "minimum_history": "20_TRADABLE_CLOSES_AND_PREVIOUS_OBSERVATION_MA20_STATE",
    "missing_observations": "PRESERVE_SUSPENSIONS_GAPS_AND_RIGHT_CENSORING",
    "exit_ambiguity": "NO_FILL_ASSUMPTION_IF_BARRIERS_SHARE_BAR_OR_QUEUE_UNKNOWN",
    "cost_status": "ASSUMPTIONS_NOT_BROKER_RECEIPTS",
    "review": "NO_RULE_TUNING_ON_OBSERVATION_WINDOW",
    "output": "RESEARCH_EVIDENCE_ONLY_NO_EXECUTION_OR_RETURN_CERTIFICATION",
}


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()


def verify(document, baseline_bytes=None):
    if not isinstance(document, dict) or set(document) != {"registration", "registration_sha256"}:
        raise ValueError("unexpected registration shape")
    registration = document["registration"]
    if not isinstance(registration, dict) or set(registration) != {
        "schema_version", "protocol", "protocol_sha256", "baseline_archive_commit",
        "baseline_archive_epoch", "research_policy",
    }:
        raise ValueError("unexpected registration fields")
    if (type(registration["schema_version"]) is not int or registration["schema_version"] != 1
        or registration["research_policy"] != POLICY
        or not re.fullmatch(r"[a-f0-9]{40}", registration["baseline_archive_commit"])
        or not re.fullmatch(r"[a-f0-9]{16}", registration["baseline_archive_epoch"])):
        raise ValueError("invalid research policy or source")
    if document["registration_sha256"] != digest(registration):
        raise ValueError("registration fingerprint mismatch")
    protocol = registration["protocol"]
    frozen = freeze(
        source_commit=protocol["source_commit"],
        baseline_artifact_sha256=protocol["negative_baseline_artifact_sha256"],
        created_at_utc=protocol["claimed_created_at_utc"],
        window_start=protocol["window_start"], window_end=protocol["window_end"],
        strategy_id=protocol["strategy_id"],
        fee_model=protocol["fee_model_assumptions_not_observed"],
        strategy_rules=protocol["frozen_strategy_rules"],
    )
    if (frozen["status"] != "CANDIDATE_FINGERPRINT_ONLY_NOT_OOS"
        or frozen["candidate"] != protocol
        or frozen["candidate_sha256"] != registration["protocol_sha256"]):
        raise ValueError("protocol fingerprint or rules mismatch")
    created = datetime.fromisoformat(protocol["claimed_created_at_utc"].replace("Z", "+00:00"))
    start = date.fromisoformat(protocol["window_start"])
    if created.astimezone(BEIJING).date() >= start:
        raise ValueError("declared creation must precede the window in Beijing time")
    if baseline_bytes is not None:
        if hashlib.sha256(baseline_bytes).hexdigest() != protocol["negative_baseline_artifact_sha256"]:
            raise ValueError("baseline bytes do not match the registered hash")
        baseline = json.loads(baseline_bytes)
        if (baseline["status"] != EVIDENCE_STATUS
            or baseline["archive_commit_sha"] != registration["baseline_archive_commit"]
            or baseline["epoch"] != registration["baseline_archive_epoch"]
            or baseline["trade_gate"] != "BLOCKED"
            or baseline["orders"] != [] or baseline["executable_candidates"] != []
            or baseline["historical_OOS_validated"] is not False
            or date.fromisoformat(baseline["validation_end"]) >= start):
            raise ValueError("baseline does not match the frozen research scope")
    return {
        "status": "VERIFIED_REGISTRATION_BYTES_NOT_TIME_ATTESTATION",
        "registration_sha256": document["registration_sha256"],
        "window_start": protocol["window_start"], "window_end": protocol["window_end"],
        "baseline_bytes_verified": baseline_bytes is not None,
        "prospective_freeze_externally_attested": False,
        "historical_OOS_validated": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    result = verify(json.loads(args.registration.read_bytes()),
                    args.baseline.read_bytes() if args.baseline else None)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
