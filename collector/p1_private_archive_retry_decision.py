"""P1 fail-closed retry decision after a possibly interrupted archive push.

Never retries the push itself. Reconcile a freshly cloned remote main SHA:
 - unchanged at frozen old parent: do not infer a push happened;
 - changed to an explicitly supplied expected new commit: verify the exact
   batch and SHA on an independent fresh checkout;
 - any other new commit: stop, investigate and rebuild from a new frozen plan.
No force push, replay, repair, or implicit authorization.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from collector.p1_independent_postpush_readback import verify

SHA = re.compile(r"[a-f0-9]{40}\Z")


def _git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        stderr=subprocess.PIPE, text=True, timeout=30).strip()


def decide(proposal, handoff, independent_checkout, old_commit, expected_new_commit=None):
    repo = Path(independent_checkout)
    if not isinstance(old_commit, str) or not SHA.fullmatch(old_commit):
        raise ValueError("old target commit not frozen")
    if (expected_new_commit is not None and
        (not isinstance(expected_new_commit, str)
         or not SHA.fullmatch(expected_new_commit)
         or expected_new_commit == old_commit)):
        raise ValueError("untrusted expected new commit")
    if not repo.is_dir() or repo.is_symlink():
        raise ValueError("fresh independent checkout missing")
    if _git(repo, "rev-parse", "--show-toplevel") != str(repo.resolve()):
        raise ValueError("not an independent checkout root")
    if _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD") != "main":
        raise ValueError("fresh checkout must be main")
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("fresh checkout is dirty")
    head = _git(repo, "rev-parse", "--verify", "HEAD")
    observed = _git(repo, "ls-remote", "--exit-code",
                    "origin", "refs/heads/main").split()
    if observed != [head, "refs/heads/main"]:
        raise ValueError("independent checkout does not match remote main")
    if (not isinstance(proposal, dict) or proposal.get("target_commit") != old_commit
        or proposal.get("trade_gate") != "BLOCKED"
        or proposal.get("orders") != []
        or proposal.get("automatic_copy_authorized") is not False
        or proposal.get("writer_cutover_authorized") is not False):
        raise ValueError("untrusted original frozen proposal")
    report = None
    if head == old_commit:
        status = "REMOTE_UNCHANGED_REPLAN_BEFORE_ANY_WRITE"
    elif expected_new_commit is not None and head == expected_new_commit:
        report = verify(proposal, handoff, repo, old_commit, expected_new_commit)
        status = "REMOTE_HAS_EXACT_SHA_BATCH_ALREADY_NO_REPLAY"
    else:
        raise ValueError("unrecognized remote main change; stop retry")
    return {
        "phase": "P1_PRIVATE_ARCHIVE_RETRY_DECISION_NO_WRITE",
        "status": status,
        "observed_remote_commit": head,
        "frozen_old_commit": old_commit,
        "expected_new_commit": expected_new_commit,
        "independent_batch_readback_passed": report is not None,
        "batch_selected_inventory_sha256": proposal.get("selected_inventory_sha256"),
        "do_not_replay_existing_batch": True,
        "git_push_performed": False,
        "git_commit_performed": False,
        "migration_performed_by_this_check": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "destination_mirror_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proposal", type=Path, required=True)
    p.add_argument("--handoff", type=Path, required=True)
    p.add_argument("--checkout", type=Path, required=True)
    p.add_argument("--old-commit", required=True)
    p.add_argument("--expected-new-commit")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = decide(json.loads(a.proposal.read_text()),
                    json.loads(a.handoff.read_text()), a.checkout,
                    a.old_commit, a.expected_new_commit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
