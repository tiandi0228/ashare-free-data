"""Presentation-only progress history. Never converts historical evidence into current acceptance."""
import argparse
import json
from pathlib import Path

PHASES = ("P0", "P1", "P2", "P3", "P4")

def _valid_baseline(value):
    if not isinstance(value, dict) or value.get("trade_gate") != "BLOCKED":
        raise ValueError("unsafe baseline")
    stages = value.get("stages")
    if not isinstance(stages, dict) or set(stages) != {"P2", "P3", "P4"}:
        raise ValueError("missing phase baseline")
    for phase in ("P2", "P3", "P4"):
        stage = stages[phase]
        if stage.get("total_weight") != 100 or len(stage.get("criteria", [])) != 10:
            raise ValueError("invalid phase denominator")
        for row in stage["criteria"]:
            if row.get("passed") is True and (
                not isinstance(row.get("evidence"), dict)
                or row["evidence"].get("source_commit") != value.get("source_commit")
                or row["evidence"].get("verification") != "OFFLINE_UNITTEST_PASSED_IN_THIS_RUN"
            ):
                raise ValueError("unverifiable passed criterion")

def summarize(current, previous=None, p1=None):
    _valid_baseline(current)
    if previous is not None:
        _valid_baseline(previous)
    if p1 is not None and (
        p1.get("trade_gate") != "BLOCKED"
        or p1.get("historical_PIT_verified") is not False
        or p1.get("phase") != "P1_DURABLE_PINNED_PROGRESS"
        or p1.get("status") != "VERIFIED_DURABLE_LEDGER_NOT_MARKET_CERTIFICATION"
        or type(p1.get("completed_shards")) is not int
        or type(p1.get("total_shards")) is not int
        or not 0 <= p1["completed_shards"] <= p1["total_shards"]
        or p1["total_shards"] == 0
        or not isinstance(p1.get("source_sha256"), str)
        or len(p1["source_sha256"]) != 64
    ):
        raise ValueError("unverified P1 epoch")
    phases = {"P0": {
        "development_pct": None, "historical_claim_pct": None,
        "verification": "NOT_EVALUATED_BY_THIS_REPORT",
        "note": "P0 needs its own current acceptance proof; prior claims are not silently certified",
    }}
    phases["P1"] = {
        "development_pct": None,
        "research_shard_coverage_pct": round(100*p1["completed_shards"]/p1["total_shards"], 4) if p1 else None,
        "completed_shards": p1["completed_shards"] if p1 else None,
        "total_shards": p1["total_shards"] if p1 else None,
        "roster_epoch_sha256": p1["source_sha256"] if p1 else None,
        "verification": "PINNED_LEDGER_ONLY_NOT_ARCHIVE_OR_PIT" if p1 else "NO_SAME_EPOCH_RECEIPT",
    }
    for name in ("P2", "P3", "P4"):
        stage = current["stages"][name]
        old = previous["stages"][name] if previous else None
        current_tests = current.get("tests_executed") is True
        current_passed = [r["id"] for r in stage["criteria"] if r.get("passed") is True] if current_tests else []
        prior_passed = [r["id"] for r in old["criteria"] if r.get("passed") is True] if old and previous.get("tests_executed") is True else []
        # Historical passes are evidence history, never reclassified as current passes.
        history = sorted(set(prior_passed) | set(current_passed))
        phases[name] = {
            "development_pct": None,
            "current_offline_acceptance_pct": stage.get("engineering_acceptance_baseline_pct") if current_tests else None,
            "historically_observed_test_criteria": history,
            "historically_observed_test_criteria_count": len(history),
            "current_passed_criteria": current_passed,
            "verification": "TESTED_THIS_RUN" if current_tests else "NOT_RERUN",
            "current_source_commit": current.get("source_commit"),
            "previous_source_commit": previous.get("source_commit") if previous else None,
            "historical_pit_certified": False,
            "note": "historical test success is not overall development completion or current acceptance",
        }
    return {
        "phase": "P0_P4_PROGRESS_SEPARATED_SNAPSHOT",
        "stages": phases,
        "trade_gate": "BLOCKED",
        "historical_PIT_verified": False,
        "orders": [],
        "executable_candidates": [],
        "production_ready": False,
        "progress_reset_from_missing_current_tests": False,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--p1", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text()) if path else None
    result = summarize(read(args.current), read(args.previous), read(args.p1))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v.get("verification") for k,v in result["stages"].items()}))

if __name__ == "__main__":
    main()
