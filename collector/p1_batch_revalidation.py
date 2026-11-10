"""Fail-closed revalidation of an earlier P1 read-only batch proposal.

Any source/target change invalidates the proposal. This does NOT copy files,
approve a migration, or attest to origin authenticity.
"""
import argparse
import json
from pathlib import Path

from collector.p1_bounded_missing_shard_batch_plan import build

_REQUIRED_FALSE = ("migration_performed", "automatic_copy_authorized",
                   "writer_cutover_authorized", "destination_mirror_verified",
                   "historical_PIT_verified")


def revalidate(proposal, handoff, source, target, source_commit, target_commit):
    if (not isinstance(proposal, dict)
        or proposal.get("phase") != "P1_BOUNDED_MISSING_SHARD_BATCH_RESEARCH_ONLY"
        or proposal.get("status") != "REVIEWABLE_MISSING_SHARD_BATCH_NO_WRITE"
        or proposal.get("trade_gate") != "BLOCKED"
        or proposal.get("orders") != []
        or proposal.get("executable_candidates") != []
        or any(proposal.get(k) is not False for k in _REQUIRED_FALSE)):
        raise ValueError("proposal not a reviewable blocked P1 batch")
    if (type(proposal.get("batch_max_shards")) is not int
        or type(proposal.get("batch_max_bytes")) is not int):
        raise ValueError("proposal limits are missing or invalid")
    current = build(handoff, source, target, source_commit, target_commit,
                    max_shards=proposal["batch_max_shards"],
                    max_bytes=proposal["batch_max_bytes"])
    # Full equality rejects stale source/target commits, altered file inventory,
    # missing/extra keys, changed SHA, reordered rows, and changed target bytes.
    if proposal != current:
        raise ValueError("stale or modified batch proposal; regenerate review evidence")
    if (not current["selected_missing_files"]
        or current["selected_file_count"] != len(current["selected_missing_files"])
        or current["selected_file_count"] > 36
        or len(current["selected_shards"]) > 4
        or current["selected_bytes"] > 25 * 1024 * 1024):
        raise ValueError("empty or unbounded P1 batch")
    return {
        "phase": "P1_BATCH_PROPOSAL_REVALIDATION_NO_WRITE",
        "status": "PROPOSAL_UNCHANGED_READ_ONLY_NOT_AUTHORIZED",
        "source_archive_commit": source_commit,
        "target_commit": target_commit,
        "source_file_inventory_sha256": current["source_file_inventory_sha256"],
        "selected_inventory_sha256": current["selected_inventory_sha256"],
        "selected_file_count": current["selected_file_count"],
        "selected_bytes": current["selected_bytes"],
        "selected_shards": current["selected_shards"],
        "migration_performed": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "destination_mirror_verified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proposal", type=Path, required=True)
    p.add_argument("--handoff", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", type=Path, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--target-commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = revalidate(json.loads(a.proposal.read_text()),
                        json.loads(a.handoff.read_text()), a.source, a.target,
                        a.source_commit, a.target_commit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
