"""Isolated, SHA-verified P1 batch staging for offline regression.

Writes ONLY a new scratch directory outside source/target roots. Does not
modify either Git repository, push a commit, or authorize a migration.
"""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from collector.p1_batch_revalidation import revalidate
from collector.p1_target_sha_readback import sha256


def stage(proposal, handoff, source, target, source_commit, target_commit, output):
    source, target, output = Path(source), Path(target), Path(output)
    # The scratch directory must be separate from both repositories.
    parent = output.parent
    if (output.exists() or output.is_symlink() or not parent.is_dir()
        or parent.is_symlink()):
        raise ValueError("stage output must be a new directory under a real parent")
    resolved = output.resolve()
    if (resolved.is_relative_to(source.resolve())
        or resolved.is_relative_to(target.resolve())
        or source.resolve().is_relative_to(resolved)
        or target.resolve().is_relative_to(resolved)):
        raise ValueError("scratch output overlaps source or target")
    checked = revalidate(proposal, handoff, source, target,
                         source_commit, target_commit)
    scratch = Path(tempfile.mkdtemp(prefix=".p1-stage-", dir=parent))
    try:
        copied = []
        for row in proposal["selected_missing_files"]:
            rel = row["path"]
            src = source / rel
            dst = scratch / "files" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            total = 0
            # A file may mutate between planning and copying: hash actual
            # copied bytes and independently rehash the staged result.
            with src.open("rb") as inp, dst.open("xb") as out:
                for block in iter(lambda: inp.read(1024 * 1024), b""):
                    out.write(block)
                    digest.update(block)
                    total += len(block)
            if (digest.hexdigest() != row["sha256"]
                or sha256(dst) != row["sha256"] or total != row["bytes"]):
                raise ValueError("staged source bytes or SHA diverged: " + rel)
            copied.append({"path": rel, "sha256": row["sha256"], "bytes": total})
        if len(copied) != checked["selected_file_count"]:
            raise ValueError("staged file count changed")
        if sum(x["bytes"] for x in copied) != checked["selected_bytes"]:
            raise ValueError("staged byte budget mismatch")
        # Fail closed if original/target state changed during staging.
        after = revalidate(proposal, handoff, source, target,
                           source_commit, target_commit)
        if after != checked:
            raise ValueError("batch changed during staging")
        report = {
            "phase": "P1_OFFLINE_BATCH_STAGING_NOT_MIGRATED",
            "status": "SCRATCH_BYTES_SHA_MATCH_NOT_DESTINATION",
            "source_archive_commit": source_commit,
            "target_commit": target_commit,
            "selected_inventory_sha256": checked["selected_inventory_sha256"],
            "staged_file_count": len(copied),
            "staged_bytes": sum(x["bytes"] for x in copied),
            "files": copied,
            "migration_performed": False,
            "automatic_copy_authorized": False,
            "writer_cutover_authorized": False,
            "destination_mirror_verified": False,
            "historical_PIT_verified": False,
            "trade_gate": "BLOCKED",
            "orders": [],
            "executable_candidates": [],
        }
        (scratch / "stage_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if output.exists() or output.is_symlink():
            raise ValueError("stage destination appeared during staging")
        scratch.rename(output)
        return report
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)


def main():
    p = argparse.ArgumentParser()
    for name in ("proposal", "handoff", "source", "target", "out"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--target-commit", required=True)
    args = p.parse_args()
    report = stage(json.loads(args.proposal.read_text()),
                   json.loads(args.handoff.read_text()), args.source,
                   args.target, args.source_commit, args.target_commit, args.out)
    print(json.dumps({k: report[k] for k in (
        "status", "staged_file_count", "staged_bytes", "trade_gate")}))


if __name__ == "__main__":
    main()
