"""Read-only P1 remote-main SHA gate; no commit, push or migration."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from collector.p1_private_git_commit_preflight import preflight

def gate(proposal, handoff, source, target_repo, scratch, source_commit, target_commit):
    local = preflight(proposal, handoff, source, target_repo, scratch,
                      source_commit, target_commit)
    output = subprocess.check_output(
        ["git", "-C", str(target_repo), "ls-remote", "--exit-code",
         "origin", "refs/heads/main"],
        text=True, stderr=subprocess.PIPE, timeout=30).strip()
    parts = output.split()
    if (len(parts) != 2 or not re.fullmatch("[a-f0-9]{40}", parts[0])
        or parts[1] != "refs/heads/main"):
        raise ValueError("remote main reference malformed")
    if parts[0] != target_commit:
        raise ValueError("remote main advanced; frozen batch is stale")
    return {
        "phase": "P1_PRIVATE_REMOTE_MAIN_SHA_PREFLIGHT_NO_WRITE",
        "status": "REMOTE_MAIN_SHA_MATCH_NOT_AUTHORIZED",
        "expected_target_commit": target_commit,
        "observed_remote_commit": parts[0],
        "source_archive_commit": source_commit,
        "selected_inventory_sha256": local["selected_inventory_sha256"],
        "file_count": local["file_count"],
        "byte_count": local["byte_count"],
        "remote_check_atomic_with_future_push": False,
        "git_push_performed": False,
        "git_commit_performed": False,
        "migration_performed": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "destination_mirror_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }

def main():
    p = argparse.ArgumentParser()
    for key in ("proposal","handoff","source","target-repo","scratch","out"):
        p.add_argument("--"+key, required=True, type=Path)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--target-commit", required=True)
    a=p.parse_args()
    report=gate(json.loads(a.proposal.read_text()),
                json.loads(a.handoff.read_text()), a.source, a.target_repo,
                a.scratch, a.source_commit, a.target_commit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))

if __name__=="__main__":
    main()
