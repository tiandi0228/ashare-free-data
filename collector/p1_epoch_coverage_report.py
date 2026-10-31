"""Read-only, epoch-pinned P1 checkpoint coverage; never a trading readiness score."""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import validate, epoch_path


def assess(ledger, requested_source_sha):
    if not isinstance(requested_source_sha, str):
        raise ValueError("explicit frozen source SHA required")
    epoch_path(requested_source_sha)
    validate(ledger)
    if ledger["source_sha256"] != requested_source_sha:
        raise ValueError("cross-epoch or legacy checkpoint rejected")
    total = ledger["shard_count"]
    completed = ledger["completed_shards"]
    return {
        "phase": "P1_READ_ONLY_EPOCH_COVERAGE",
        "source_sha256": requested_source_sha,
        "checkpoint_type": "explicit_epoch_only",
        "completed_shards": completed,
        "total_shards": total,
        "pending_shards": total - completed,
        "completed_issuers": ledger["completed_issuers"],
        "historical_data_collection_percent": round(100 * completed / total, 2),
        "full_market_bars_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
        "warning": "Checkpoint digest metadata only; original CSV archive replay and trading eligibility are NOT certified.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--checkpoint", required=True, help="Explicit epoch JSON, not a generic legacy pointer")
    parser.add_argument("--out")
    args = parser.parse_args()
    path = Path(args.checkpoint)
    if path.name != args.source_sha + ".json" or path.parent.name != "checkpoints":
        raise ValueError("checkpoint file must be an explicit checkpoints/<source-sha>.json epoch")
    result = assess(json.loads(path.read_text(encoding="utf-8")), args.source_sha)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
