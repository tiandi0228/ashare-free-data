"""Read-only independent post-push audit of one bounded private P1 Git batch.

This never creates, pushes, deletes or modifies a Git commit. The caller must
supply an independently cloned checkout of the exact remote main commit. A
local file copy alone is not proof: commit ancestry, added-only paths, remote
head, source SHA inventory, and every selected file's bytes are all checked.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from collector.p1_private_git_commit_preflight import ARCHIVE
from collector.p1_target_sha_readback import reconcile, sha256

COMMIT = re.compile(r"[a-f0-9]{40}\Z")


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.PIPE,
        timeout=30).decode("utf-8").strip()


def verify(proposal, handoff, independent_checkout, old_commit, new_commit):
    repo = Path(independent_checkout)
    if (not isinstance(old_commit, str) or not COMMIT.fullmatch(old_commit)
        or not isinstance(new_commit, str) or not COMMIT.fullmatch(new_commit)
        or old_commit == new_commit):
        raise ValueError("expected distinct immutable old/new commit SHAs")
    if not repo.is_dir() or repo.is_symlink():
        raise ValueError("independent checkout unavailable")
    if git(repo, "rev-parse", "--show-toplevel") != str(repo.resolve()):
        raise ValueError("not the independent Git checkout root")
    if git(repo, "symbolic-ref", "--quiet", "--short", "HEAD") != "main":
        raise ValueError("independent checkout must be on main")
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("independent checkout has local modifications")
    if git(repo, "rev-parse", "--verify", "HEAD") != new_commit:
        raise ValueError("independent checkout is not the new commit")
    parents = git(repo, "rev-list", "--parents", "-n", "1", new_commit).split()
    if parents != [new_commit, old_commit]:
        raise ValueError("batch commit must have exact frozen parent")
    remote = git(repo, "ls-remote", "--exit-code", "origin", "refs/heads/main").split()
    if remote != [new_commit, "refs/heads/main"]:
        raise ValueError("independent remote main not at audited new commit")
    if (not isinstance(proposal, dict)
        or proposal.get("phase") != "P1_BOUNDED_MISSING_SHARD_BATCH_RESEARCH_ONLY"
        or proposal.get("status") != "REVIEWABLE_MISSING_SHARD_BATCH_NO_WRITE"
        or proposal.get("target_commit") != old_commit
        or proposal.get("trade_gate") != "BLOCKED"
        or proposal.get("orders") != []
        or proposal.get("executable_candidates") != []
        or any(proposal.get(k) is not False for k in (
            "migration_performed", "automatic_copy_authorized",
            "writer_cutover_authorized", "destination_mirror_verified",
            "historical_PIT_verified"))):
        raise ValueError("untrusted or stale original batch plan")
    selected = proposal.get("selected_missing_files")
    if (not isinstance(selected, list) or not 1 <= len(selected) <= 36
        or proposal.get("selected_file_count") != len(selected)
        or len(proposal.get("selected_shards", [])) > 4
        or type(proposal.get("selected_bytes")) is not int
        or not 0 <= proposal["selected_bytes"] <= 25 * 1024 * 1024):
        raise ValueError("unbounded selected batch")
    if not isinstance(handoff, dict) or (
        proposal.get("source_file_inventory_sha256") !=
        handoff.get("source_file_inventory_sha256")):
        raise ValueError("source handoff mismatch")
    originals = handoff.get("original_paths_and_sha256")
    if not isinstance(originals, list):
        raise ValueError("missing sealed source inventory")
    allowed = {r["path"]: r["sha256"] for r in originals}
    expected_paths = set()
    expected_bytes = 0
    for row in selected:
        if (not isinstance(row, dict)
            or set(row) != {"path", "sha256", "bytes"}
            or row["path"] in expected_paths
            or allowed.get(row["path"]) != row["sha256"]
            or type(row["bytes"]) is not int or row["bytes"] < 0):
            raise ValueError("selected path absent from sealed source inventory")
        expected_paths.add(row["path"])
        expected_bytes += row["bytes"]
    if expected_bytes != proposal["selected_bytes"]:
        raise ValueError("selected byte total changed")
    canonical = json.dumps(selected, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    if hashlib.sha256(canonical).hexdigest() != proposal.get("selected_inventory_sha256"):
        raise ValueError("frozen selected inventory SHA mismatch")
    if (not isinstance(proposal.get("source_archive_commit"), str)
        or not COMMIT.fullmatch(proposal["source_archive_commit"])):
        raise ValueError("source archive commit is not pinned")
    # Validate entire target against canonical allowlist (and its inventory
    # digest) before accepting any selected file as matching SHA.
    readback = reconcile(handoff, repo / ARCHIVE, new_commit)
    if readback["conflicting_file_count"] or readback["unallowlisted_target_file_count"]:
        raise ValueError("independent target readback has conflicting originals")
    # -z preserves arbitrary file names (though source rows enforce strict names).
    changed = subprocess.check_output([
        "git", "-C", str(repo), "diff", "--name-status", "--no-renames",
        "-z", old_commit, new_commit, "--"],
        stderr=subprocess.PIPE, timeout=30)
    fields = changed.decode("utf-8").split("\x00")
    if fields[-1] != "":
        raise ValueError("malformed Git changed-path records")
    fields.pop()
    if len(fields) % 2:
        raise ValueError("malformed Git name/status pairs")
    changed_paths = {}
    for i in range(0, len(fields), 2):
        status, fullpath = fields[i:i + 2]
        if status != "A" or not fullpath.startswith(ARCHIVE.as_posix() + "/"):
            raise ValueError("commit changed non-allowlisted or existing path")
        rel = fullpath[len(ARCHIVE.as_posix()) + 1:]
        if rel in changed_paths:
            raise ValueError("duplicate added path in Git diff")
        changed_paths[rel] = status
    if set(changed_paths) != expected_paths:
        raise ValueError("commit additions differ from frozen selected batch")
    for row in selected:
        path = repo / ARCHIVE / row["path"]
        if (not path.is_file() or path.is_symlink()
            or path.stat().st_size != row["bytes"]
            or sha256(path) != row["sha256"]):
            raise ValueError("independently cloned original SHA mismatch")
    return {
        "phase": "P1_INDEPENDENT_POST_PUSH_BATCH_AUDIT_NO_TRADE",
        "status": "SELECTED_GIT_ADDITIONS_SHA_MATCH_NOT_FULL_MIGRATION",
        "previous_target_commit": old_commit,
        "new_target_commit": new_commit,
        "source_file_inventory_sha256": readback["source_file_inventory_sha256"],
        "selected_inventory_sha256": proposal["selected_inventory_sha256"],
        "added_file_count": len(changed_paths),
        "added_bytes": expected_bytes,
        "total_allowlisted_files": readback["allowlisted_files"],
        "total_matching_files": readback["matching_file_count"],
        "total_missing_files": readback["missing_file_count"],
        "commit_scoped_selected_bytes_verified": True,
        "whole_destination_mirror_certified": False,
        "writer_cutover_authorized": False,
        "automatic_copy_authorized": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    for field in ("proposal", "handoff", "checkout", "out"):
        p.add_argument("--" + field, type=Path, required=True)
    p.add_argument("--old-commit", required=True)
    p.add_argument("--new-commit", required=True)
    a = p.parse_args()
    report = verify(json.loads(a.proposal.read_text()),
                    json.loads(a.handoff.read_text()), a.checkout,
                    a.old_commit, a.new_commit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
