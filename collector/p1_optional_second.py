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



def verify_second_capture(plan, manifest_root, second_index, folder):
    """Independent source/CSV replay before optional second can be archived."""
    from collector.p1_quad_verify import verify
    p = json.loads(Path(plan).read_text())
    verified = verify(p, [(int(second_index), Path(folder))], Path(manifest_root))
    if (verified.get("verified_shards") != 1
            or verified.get("verified_issuers") != p["shards"][int(second_index)]["count"]
            or verified.get("trade_gate") != "BLOCKED"
            or verified.get("historical_PIT_verified") is not False):
        raise ValueError("unsafe second-shard independent verification")
    return verified


def accept_verified_second(result, plan, manifest_root, folder):
    """Keep the first shard when optional evidence is incomplete or inconsistent."""
    if not result["accepted_second"]:
        return result
    try:
        details = verify_second_capture(
            plan, manifest_root, result["second_shard_index"], folder)
    except (ValueError, OSError, KeyError, TypeError, UnicodeError, IndexError) as exc:
        result.update(
            accepted_second=False, effective_shard_count=1,
            status="SECOND_INVALID_PRESERVE_FIRST",
            second_rejection_type=type(exc).__name__,
            second_verification_passed=False,
        )
    else:
        result.update(
            status="SECOND_SHARD_VERIFIED",
            second_verification_passed=True,
            second_verified_issuers=details["verified_issuers"],
        )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requested-second", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--manifest-root", required=True)
    parser.add_argument("--second-folder", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = decide(args.requested_second, args.outcome, args.second)
    result = accept_verified_second(result, args.plan, args.manifest_root, args.second_folder)
    dest = Path(args.report)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    with Path(args.output_file).open("a") as handle:
        handle.write("has_second=" + str(result["accepted_second"]).lower() + "\n")
    if result["status"] in ("SECOND_FAILED_PRESERVE_FIRST", "SECOND_INVALID_PRESERVE_FIRST"):
        print("::warning title=Optional second shard failed::Preserving and auditing the successful first research shard")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
