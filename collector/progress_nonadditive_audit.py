"""Read-only, non-additive P1/P2 progress reconciliation. Never certifies trades."""
import json
from pathlib import Path

def reconcile(p1, p2_history):
    if not isinstance(p1, dict) or p1.get("phase") != "P1_ROSTER_SHARD_LEDGER":
        raise ValueError("unexpected P1 checkpoint type")
    count, total, completed = p1.get("completed_shards"), p1.get("shard_count"), p1.get("completed")
    if type(count) is not int or type(total) is not int or total <= 0 or count < 0 or count > total:
        raise ValueError("invalid P1 counter")
    if not isinstance(completed, list) or len(completed) != count:
        raise ValueError("P1 ledger count mismatch")
    indexes = [r.get("index") if isinstance(r, dict) else None for r in completed]
    if any(type(i) is not int or i < 0 or i >= total for i in indexes) or len(set(indexes)) != count:
        raise ValueError("P1 duplicate or invalid shard index")
    source = p1.get("source_sha256")
    if not isinstance(source, str) or len(source) != 64 or any(c not in "0123456789abcdef" for c in source):
        raise ValueError("invalid source SHA256")
    if not isinstance(p2_history, list) or not p2_history:
        raise ValueError("missing separately labeled P2 historical records")
    records = []
    for row in p2_history:
        if not isinstance(row, dict) or row.get("kind") != "PREVIOUSLY_REPORTED_NOT_REPLAYED_THIS_RUN":
            raise ValueError("historical P2 records must remain unverified")
        n, d = row.get("feature_complete_shards"), row.get("observed_shards")
        if type(n) is not int or type(d) is not int or not 0 <= n <= d <= 400:
            raise ValueError("invalid P2 historical coverage")
        day = row.get("reported_day")
        if not isinstance(day, str) or len(day) != 10:
            raise ValueError("invalid historical record date")
        records.append({"reported_day": day, "feature_complete_shards": n,
                        "observed_shards": d, "verification": "HISTORICAL_UNREPLAYED"})
    return {
        "status": "NON_ADDITIVE_DIFFERENT_PROVENANCE",
        "P1": {"research_roster_checkpoint": count, "denominator": total,
               "source_sha256": source, "archive_completed_verified": False},
        "P2": {"reported_history": records, "current_feature_coverage_verified": None},
        "combined_shards": None, "overall_completion_pct": None,
        "historical_PIT_verified": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
        "next_required": "independently replay original CSV and reconcile source epoch/manifest before promoting counters"
    }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=Path("evidence/p1_checkpoint.json"))
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reconcile(json.loads(args.checkpoint.read_text()),
                       json.loads(args.history.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
