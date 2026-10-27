"""Read-only comparison of two unverified P1 roster epochs.

Matching hashes are consistency evidence, never authority to merge histories.
"""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import validate


def compare(left, right):
    validate(left)
    validate(right)
    a = {item["index"]: item for item in left["completed"]}
    b = {item["index"]: item for item in right["completed"]}
    common = sorted(set(a) & set(b))
    left_only = sorted(set(a) - set(b))
    right_only = sorted(set(b) - set(a))
    matching_manifests = [i for i in common if a[i]["manifest_sha256"] == b[i]["manifest_sha256"]]
    matching_receipts = [i for i in matching_manifests if a[i]["receipt_sha256"] == b[i]["receipt_sha256"]]
    return {
        "phase": "P1_READ_ONLY_EPOCH_COMPARISON",
        "left_source_sha256": left["source_sha256"],
        "right_source_sha256": right["source_sha256"],
        "left_completed_shards": len(a),
        "right_completed_shards": len(b),
        "overlapping_completed_shards": len(common),
        "left_only_completed_shards": len(left_only),
        "right_only_completed_shards": len(right_only),
        "left_only_indices": left_only,
        "right_only_indices": right_only,
        "matching_manifest_shards": len(matching_manifests),
        "matching_manifest_and_receipt_shards": len(matching_receipts),
        "conflicting_overlapping_shards": [i for i in common if i not in matching_receipts],
        "whole_roster_membership_verified": False,
        "cross_epoch_reuse_authorized": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = compare(json.loads(Path(args.left).read_text()), json.loads(Path(args.right).read_text()))
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
