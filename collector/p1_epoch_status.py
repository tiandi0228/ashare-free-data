"""Read-only P1 status by explicit roster epoch; never sum incompatible pools.

Usage: python -m collector.p1_epoch_status --root evidence/checkpoints
Each source SHA is an independent data universe; highest count is not
necessarily the currently approved epoch and cannot certify market coverage.
"""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import validate, epoch_path


def summarize(checkpoints):
    if not isinstance(checkpoints, dict):
        raise ValueError("epoch to checkpoint mapping required")
    rows = []
    for source_sha, ledger in sorted(checkpoints.items()):
        if epoch_path(source_sha) != "evidence/checkpoints/" + source_sha + ".json":
            raise ValueError("invalid epoch path")
        validate(ledger)
        if ledger["source_sha256"] != source_sha:
            raise ValueError("checkpoint source SHA does not match epoch")
        rows.append({
            "source_sha256": source_sha,
            "completed_shards": ledger["completed_shards"],
            "total_shards": ledger["shard_count"],
            "pending_shards": len(ledger["pending_shards"]),
            "completed_issuers": ledger["completed_issuers"],
            "checkpoint_percent": round(
                100 * ledger["completed_shards"] / ledger["shard_count"], 2
            ),
            "full_market_bars_certified": False,
            "historical_PIT_verified": False,
            "trade_gate": "BLOCKED",
        })
    return {
        "phase": "P1_INDEPENDENT_EPOCH_STATUS",
        "status": "RESEARCH_CHECKPOINTS_ONLY",
        "epochs": rows,
        "approved_active_source_sha256": None,
        "combined_completed_shards": None,
        "combined_coverage_percent": None,
        "cross_epoch_merge_authorized": False,
        "full_market_bars_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
        "warning": "No active epoch inferred from counts or filenames. Data-source SHA epochs cannot be pooled.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("evidence/checkpoints"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    paths = sorted(args.root.glob("*.json"))
    data = {}
    for path in paths:
        sha = path.stem
        epoch_path(sha)
        if sha in data:
            raise ValueError("duplicate epoch")
        data[sha] = json.loads(path.read_text(encoding="utf-8"))
    result = summarize(data)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
