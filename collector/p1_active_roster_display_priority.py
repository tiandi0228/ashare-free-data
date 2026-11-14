"""P1 display-source selection: valid active roster beats unrelated legacy alias.

Read-only research metadata. No archive copy, write target changes or trades.
"""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import epoch_path, validate
from collector.p1_current_progress import report


def reconcile(active_roster, active_checkpoint, legacy_checkpoint=None):
    # report independently checks canonical roster bytes, digest and active ledger.
    active = report(active_roster, active_checkpoint)
    digest = active["source_sha256"]
    old = None
    if legacy_checkpoint is not None:
        validated = validate(legacy_checkpoint)
        old = {
            "source_sha256": validated["source_sha256"],
            "completed_shards": validated["completed_shards"],
            "total_shards": validated["shard_count"],
            "is_active_roster": validated["source_sha256"] == digest,
        }
    return {
        "phase": "P1_ACTIVE_ROSTER_DISPLAY_PRIORITY",
        "status": "ACTIVE_SOURCE_PINNED_RESEARCH_CHECKPOINT",
        "active_epoch_checkpoint_path": epoch_path(digest),
        "active": {
            "source_sha256": digest,
            "completed_shards": active["completed_shards"],
            "total_shards": active["total_shards"],
            "completed_issuers": active["completed_issuers"],
            "coverage_pct": active["research_coverage_percent"],
        },
        "legacy_alias": old,
        "alias_replaces_active_source": False,
        "cross_epoch_counts_addable": False,
        "all_original_CSV_bytes_independently_replayed_this_run": False,
        "overall_P1_project_completion_pct": None,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    lock = json.loads((root / "evidence/p1_active_roster.json").read_text())
    current = json.loads((root / epoch_path(lock["source_sha256"])).read_text())
    oldpath = root / "evidence/p1_checkpoint.json"
    old = json.loads(oldpath.read_text()) if oldpath.is_file() else None
    result = reconcile(lock, current, old)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
