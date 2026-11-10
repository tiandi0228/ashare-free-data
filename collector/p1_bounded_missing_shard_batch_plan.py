"""Bounded, deterministic, read-only P1 missing-shard transfer plan.

This emits an operator-review artifact, NOT copy instructions, permission,
or evidence of target migration. Source handoff provenance and full byte replay
must be established separately; selected source shard bytes are rehashed here.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from collector.p1_target_sha_readback import reconcile, sha256

COMMIT = re.compile(r"[a-f0-9]{40}\Z")
MAX_BATCH_SHARDS = 4
MAX_BATCH_BYTES = 25 * 1024 * 1024
MAX_BATCH_FILES = MAX_BATCH_SHARDS * 9


def _safe_file(root, rel):
    path = root / rel
    if root.is_symlink() or any(
        p.is_symlink() for p in (root, *[root.joinpath(*Path(rel).parts[:i])
                                      for i in range(1, len(Path(rel).parts) + 1)])
    ) or not path.is_file():
        raise ValueError("missing, symlinked, or nonregular original: " + rel)
    return path


def build(handoff, source, target, source_commit, target_commit,
          max_shards=MAX_BATCH_SHARDS, max_bytes=MAX_BATCH_BYTES):
    if (not isinstance(source_commit, str) or not COMMIT.fullmatch(source_commit)
        or type(max_shards) is not int or not 1 <= max_shards <= MAX_BATCH_SHARDS
        or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BATCH_BYTES):
        raise ValueError("invalid source commit or bounded batch limits")
    source = Path(source)
    target = Path(target)
    if not source.is_dir() or source.is_symlink():
        raise ValueError("source archive unavailable or symlinked")
    result = reconcile(handoff, target, target_commit)
    if (result["conflicting_file_count"] or result["unallowlisted_target_file_count"]):
        raise ValueError("target has conflicting or unallowlisted files")
    if (result["trade_gate"] != "BLOCKED" or result["orders"] != []
        or result["destination_mirror_verified"] is not False):
        raise ValueError("target readback gate violated")
    expected = {x["path"]: x["sha256"] for x in handoff["original_paths_and_sha256"]}
    missing = {x for x in expected if not (target / x).is_file()}
    groups = {}
    for rel in sorted(expected):
        shard = "/".join(rel.split("/")[:2])
        groups.setdefault(shard, []).append(rel)
    selected = []
    selected_shards = []
    planned_bytes = 0
    first_too_large = False
    for shard, files in sorted(groups.items()):
        to_add = [p for p in files if p in missing]
        if not to_add:
            continue
        if (len(files) < 2 or len(files) > 9
            or sum(p.endswith("/quality.json") for p in files) != 1):
            raise ValueError("incomplete handoff shard grouping")
        # Never split a shard across different batches. If one is too large,
        # fail closed rather than jumping over it and hiding the obstruction.
        if len(selected_shards) >= max_shards or len(selected) + len(to_add) > MAX_BATCH_FILES:
            break
        measured = []
        shard_bytes = 0
        for rel in files:
            path = _safe_file(source, rel)
            if sha256(path) != expected[rel]:
                raise ValueError("selected source original SHA mismatch: " + rel)
            if rel in missing:
                size = path.stat().st_size
                shard_bytes += size
                measured.append({"path": rel, "sha256": expected[rel], "bytes": size})
        if planned_bytes + shard_bytes > max_bytes:
            first_too_large = not selected_shards
            break
        selected_shards.append(shard)
        selected.extend(measured)
        planned_bytes += shard_bytes
    canonical = json.dumps(selected, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    return {
        "phase": "P1_BOUNDED_MISSING_SHARD_BATCH_RESEARCH_ONLY",
        "status": ("FIRST_MISSING_SHARD_EXCEEDS_BUDGET_NO_WRITE" if first_too_large
                   else "REVIEWABLE_MISSING_SHARD_BATCH_NO_WRITE" if selected
                   else "NO_MISSING_ALLOWLIST_FILES" if not missing
                   else "NO_BATCH_SELECTED_NO_WRITE"),
        "source_archive_commit": source_commit,
        "target_commit": target_commit,
        "source_file_inventory_sha256": handoff["source_file_inventory_sha256"],
        "source_allowlisted_file_count": len(expected),
        "target_matching_file_count": result["matching_file_count"],
        "target_missing_file_count": result["missing_file_count"],
        "selected_shards": selected_shards,
        "selected_missing_files": selected,
        "selected_file_count": len(selected),
        "selected_bytes": planned_bytes,
        "selected_inventory_sha256": hashlib.sha256(canonical).hexdigest(),
        "batch_max_shards": max_shards,
        "batch_max_bytes": max_bytes,
        "unselected_missing_files": len(missing) - len(selected),
        "source_whole_archive_replayed_by_this_plan": False,
        "destination_mirror_verified": False,
        "migration_performed": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--handoff", required=True, type=Path)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--target", required=True, type=Path)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--target-commit", required=True)
    p.add_argument("--max-shards", type=int, default=MAX_BATCH_SHARDS)
    p.add_argument("--max-bytes", type=int, default=MAX_BATCH_BYTES)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = build(json.loads(args.handoff.read_text()), args.source,
                   args.target, args.source_commit, args.target_commit,
                   args.max_shards, args.max_bytes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "status", "selected_shards", "selected_file_count", "selected_bytes",
        "unselected_missing_files", "trade_gate")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
