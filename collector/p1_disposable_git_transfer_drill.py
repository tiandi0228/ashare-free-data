"""End-to-end P1 SHA batch migration drill in a disposable LOCAL Git sandbox.

Deliberately INCOMPATIBLE with real private GitHub repositories and network
remotes: all repositories must be local siblings under a sandbox carrying a
test-only marker. Not a production writer, no credentials or schedules.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from collector.p1_private_git_commit_preflight import ARCHIVE
from collector.p1_private_remote_main_gate import gate
from collector.p1_independent_postpush_readback import verify
from collector.p1_target_sha_readback import sha256

MARKER = ".p1_disposable_sandbox_only"


def _git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True, stderr=subprocess.PIPE, timeout=30).strip()


def drill(proposal, handoff, source, local_checkout, scratch, source_commit, old_commit):
    source, local_checkout, scratch = map(Path, (source, local_checkout, scratch))
    sandbox = local_checkout.parent.resolve()
    marker = sandbox / MARKER
    if (not marker.is_file() or marker.is_symlink()
        or marker.read_text().strip() != "P1_DISPOSABLE_TEST_ONLY"
        or sandbox.is_symlink()):
        raise ValueError("disposable test sandbox marker required")
    for path in (source, local_checkout, scratch):
        if (not path.is_dir() or path.is_symlink()
            or path.resolve().parent != sandbox):
            raise ValueError("all test inputs must be sandbox sibling directories")
    remote_path = _git(local_checkout, "remote", "get-url", "origin")
    # Strictly local absolute-path bare Git remote. No HTTP, SSH, file://,
    # relative remotes or symlinked remote roots.
    remote = Path(remote_path)
    if (not remote.is_absolute() or remote.is_symlink()
        or remote.resolve().parent != sandbox
        or _git(remote, "rev-parse", "--is-bare-repository") != "true"):
        raise ValueError("real or non-disposable Git remote forbidden")
    if (proposal.get("target_commit") != old_commit
        or proposal.get("trade_gate") != "BLOCKED"):
        raise ValueError("frozen proposal mismatch")
    old_result = gate(proposal, handoff, source, local_checkout, scratch,
                      source_commit, old_commit)
    if old_result["observed_remote_commit"] != old_commit:
        raise ValueError("remote parent changed before test transfer")
    rows = proposal["selected_missing_files"]
    for row in rows:
        rel = row["path"]
        destination = local_checkout / ARCHIVE / rel
        staged = scratch / "files" / rel
        if destination.exists() or destination.is_symlink():
            raise ValueError("never overwrite target original")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with staged.open("rb") as src, destination.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        if sha256(destination) != row["sha256"]:
            raise ValueError("copied test original SHA mismatch")
    subprocess.run(["git", "-C", str(local_checkout), "add", "--",
                    *[str(ARCHIVE / r["path"]) for r in rows]],
                   check=True, timeout=30, capture_output=True)
    staged_paths = _git(local_checkout, "diff", "--cached", "--name-only").splitlines()
    expected_paths = sorted(str(ARCHIVE / row["path"]) for row in rows)
    if sorted(staged_paths) != expected_paths:
        raise ValueError("test Git index contains unexpected additions")
    subprocess.run(["git", "-C", str(local_checkout), "commit", "-qm",
                    "test-only P1 SHA batch transfer"], check=True, timeout=30)
    new_commit = _git(local_checkout, "rev-parse", "HEAD")
    if _git(local_checkout, "rev-parse", "HEAD^") != old_commit:
        raise ValueError("test commit parent changed")
    # Ordinary non-force fast-forward push. A concurrently advanced remote
    # rejects it; absolutely no --force or ref-rewrite in this module.
    subprocess.run(["git", "-C", str(local_checkout), "push", "origin",
                    "HEAD:refs/heads/main"], check=True, timeout=30,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    auditor = Path(tempfile.mkdtemp(prefix="p1-independent-", dir=sandbox))
    try:
        subprocess.run(["git", "clone", "-q", "-b", "main",
                        str(remote), str(auditor)], check=True, timeout=30)
        verified = verify(proposal, handoff, auditor, old_commit, new_commit)
    finally:
        shutil.rmtree(auditor)
    if not verified["commit_scoped_selected_bytes_verified"]:
        raise ValueError("independent SHA readback failed")
    return {
        "phase": "P1_DISPOSABLE_GIT_TRANSFER_DRILL_ONLY",
        "status": "DISPOSABLE_NONFORCE_PUSH_INDEPENDENT_SHA_MATCH",
        "old_commit": old_commit,
        "new_test_commit": new_commit,
        "test_files": verified["added_file_count"],
        "test_bytes": verified["added_bytes"],
        "real_private_repo_modified": False,
        "real_migration_performed": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
