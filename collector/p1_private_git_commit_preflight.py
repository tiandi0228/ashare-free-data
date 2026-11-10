"""Read-only preflight for a *future*, manually approved private Git batch commit.

No Git add/commit/push and no target-file writes occur here. Revalidates the
bounded P1 proposal, isolated scratch bytes, clean private main checkout and
absence of all destination paths. The remote branch must be checked again by
an independent future writer before any non-force update.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from collector.p1_batch_revalidation import revalidate
from collector.p1_target_sha_readback import sha256

SHA = re.compile(r"[a-f0-9]{40}\Z")
ARCHIVE = Path("ashare_data/research-csv-archive")


def _git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args],
                                   text=True, stderr=subprocess.PIPE).strip()


def preflight(proposal, handoff, source, target_repo, scratch, source_commit,
              target_commit):
    source = Path(source)
    target_repo = Path(target_repo)
    scratch = Path(scratch)
    if not SHA.fullmatch(target_commit) or not SHA.fullmatch(source_commit):
        raise ValueError("unfrozen Git commit")
    if (not target_repo.is_dir() or target_repo.is_symlink()
        or not scratch.is_dir() or scratch.is_symlink()):
        raise ValueError("missing real target checkout or isolated scratch")
    if _git(target_repo, "rev-parse", "--show-toplevel") != str(target_repo.resolve()):
        raise ValueError("target must be exact Git checkout root")
    if _git(target_repo, "symbolic-ref", "--quiet", "--short", "HEAD") != "main":
        raise ValueError("private target must be checked out on main")
    if _git(target_repo, "rev-parse", "--verify", "HEAD") != target_commit:
        raise ValueError("private target HEAD changed")
    if _git(target_repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("target checkout must be clean")
    root = target_repo / ARCHIVE
    if not root.is_dir() or root.is_symlink():
        raise ValueError("private archive root missing or symlinked")
    current = revalidate(proposal, handoff, source, root,
                         source_commit, target_commit)
    receipt = json.loads((scratch / "stage_report.json").read_text())
    expected = proposal["selected_missing_files"]
    if (receipt.get("phase") != "P1_OFFLINE_BATCH_STAGING_NOT_MIGRATED"
        or receipt.get("status") != "SCRATCH_BYTES_SHA_MATCH_NOT_DESTINATION"
        or receipt.get("source_archive_commit") != source_commit
        or receipt.get("target_commit") != target_commit
        or receipt.get("selected_inventory_sha256") != current["selected_inventory_sha256"]
        or receipt.get("files") != expected
        or receipt.get("staged_file_count") != len(expected)
        or receipt.get("staged_bytes") != current["selected_bytes"]
        or receipt.get("trade_gate") != "BLOCKED"
        or receipt.get("orders") != []
        or receipt.get("executable_candidates") != []
        or any(receipt.get(key) is not False for key in (
            "migration_performed", "automatic_copy_authorized",
            "writer_cutover_authorized", "destination_mirror_verified",
            "historical_PIT_verified"))):
        raise ValueError("scratch staging receipt does not match frozen plan")
    for row in expected:
        rel = row["path"]
        staged = scratch / "files" / rel
        destination = root / rel
        if (not staged.is_file() or staged.is_symlink()
            or not staged.resolve().is_relative_to((scratch / "files").resolve())
            or staged.stat().st_size != row["bytes"]
            or sha256(staged) != row["sha256"]):
            raise ValueError("staged bytes mismatch: " + rel)
        if destination.exists() or destination.is_symlink():
            raise ValueError("private destination exists: " + rel)
        if any(parent.is_symlink() for parent in destination.parents
               if parent == root or root in parent.parents):
            raise ValueError("private destination has symlink parent: " + rel)
        # Prevent a previously tracked but deleted path from being silently
        # treated as a new archival original.
        if _git(target_repo, "ls-files", "--", str(ARCHIVE / rel)):
            raise ValueError("target path already tracked in Git index: " + rel)
    return {
        "phase": "P1_PRIVATE_GIT_BATCH_PREFLIGHT_RESEARCH_ONLY",
        "status": "LOCAL_MAIN_CLEAN_SHA_STAGED_NO_WRITE_AUTHORIZED",
        "target_commit": target_commit,
        "source_archive_commit": source_commit,
        "selected_inventory_sha256": current["selected_inventory_sha256"],
        "file_count": len(expected),
        "byte_count": current["selected_bytes"],
        "git_add_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "destination_mirror_verified": False,
        "migration_performed": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    for name in ("proposal", "handoff", "source", "target-repo", "scratch", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--target-commit", required=True)
    args = p.parse_args()
    result = preflight(json.loads(args.proposal.read_text()),
                       json.loads(args.handoff.read_text()), args.source,
                       args.target_repo, args.scratch, args.source_commit,
                       args.target_commit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
