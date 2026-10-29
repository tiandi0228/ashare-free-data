"""Bounded optional second-shard acceptance. First verified shard always remains mandatory.

This policy changes only the accounting for a research pilot. A failed optional
second acquisition must not discard a separately completed first shard.
Never certifies market data or authorizes a trade.
"""
import argparse
import json
from pathlib import Path


def decide(requested, outcome, second):
    if requested not in ("true", "false"):
        raise ValueError("invalid optional-shard selection flag")
    if outcome not in ("success", "failure", "skipped"):
        raise ValueError("invalid optional-shard step outcome")
    if requested == "false":
        if outcome != "skipped" or second != "NONE":
            raise ValueError("unexpected second acquisition in single-shard run")
        accepted = False
        status = "SINGLE_SHARD_REQUESTED"
    else:
        if type(second) is not str or len(second) != 4 or not second.isdigit():
            raise ValueError("invalid second shard index")
        if outcome == "skipped":
            raise ValueError("requested second acquisition did not execute")
        accepted = outcome == "success"
        status = ("SECOND_SHARD_CAPTURED"
                  if accepted else "SECOND_FAILED_PRESERVE_FIRST")
    return {
        "phase": "P1_OPTIONAL_SECOND_SHARD_POLICY",
        "requested_second": requested == "true",
        "second_step_outcome": outcome,
        "second_shard_index": int(second) if requested == "true" else None,
        "accepted_second": accepted,
        "effective_shard_count": 1 + int(accepted),
        "status": status,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requested-second", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = decide(args.requested_second, args.outcome, args.second)
    dest = Path(args.report)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    with Path(args.output_file).open("a") as handle:
        handle.write("has_second=" + str(result["accepted_second"]).lower() + "\n")
    if result["status"] == "SECOND_FAILED_PRESERVE_FIRST":
        print("::warning title=Optional second shard failed::Preserving and auditing the successful first research shard")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
