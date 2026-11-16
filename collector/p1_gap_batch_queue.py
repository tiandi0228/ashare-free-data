"""Build a pinned, read-only queue of at most two P1 shards per dispatch."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from collector.p1_checkpoint import epoch_path
from collector.p1_fresh_shard_plan import plan as build_plan
from collector.p1_prewrite_gap_guard import check
from collector.p1_quad_pick import verify_prior_for_selection
from collector.p1_roster_lock import unpack


def queue(plan, ledger, status, archive_ids):
    verify_prior_for_selection(plan, ledger)
    pending = ledger["pending_shards"]
    archived = status.get("archived_shards")
    if (not isinstance(archived, list) or any(type(i) is not int for i in archived)
            or sorted(archive_ids) != sorted(archived)):
        raise ValueError("archive index does not match actual Git shard directories")
    if pending:
        check(plan, pending[:2], ledger, ledger, status)
    elif (len(archived) != plan["shard_count"] or sorted(archived) != list(range(plan["shard_count"]))
          or status.get("source_sha256") != plan["source_sha256"] or status.get("trade_gate") != "BLOCKED"):
        raise ValueError("completed checkpoint does not match archive")
    batches = []
    for first in range(0, len(pending), 2):
        indices = pending[first:first + 2]
        shards = [plan["shards"][i] for i in indices]
        batches.append({
            "shard_indices": indices,
            "expected_issuers": sum(s["count"] for s in shards),
            "manifest_sha256": [s["sha256"] for s in shards],
            "dispatch_preview": {"gap_window": f"{indices[0]}:{indices[-1]}",
                                 "shards_per_run": str(len(indices))},
        })
    return {
        "status": "PINNED_GAP_QUEUE_RECHECK_BEFORE_EACH_DISPATCH",
        "source_sha256": plan["source_sha256"],
        "completed_shards": ledger["completed_shards"],
        "total_shards": plan["shard_count"],
        "pending_shards": len(pending),
        "pending_issuers": sum(b["expected_issuers"] for b in batches),
        "batches": batches,
        "archive_index_parity_checked": True,
        "archive_original_csvs_replayed": False,
        "vendor_requests": 0, "archive_writes": 0, "trade_gate": "BLOCKED",
        "permission_to_write_or_trade": False, "orders": [], "executable_candidates": [],
    }


def from_git(repo, main_sha, archive_sha):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], timeout=30)

    def read(commit, path):
        return json.loads(git("show", f"{commit}:{path}"))

    for sha in (main_sha, archive_sha):
        if re.fullmatch(r"[a-f0-9]{40}", sha) is None or git("cat-file", "-t", sha).strip() != b"commit":
            raise ValueError("exact Git commit SHA required")
    lock = read(main_sha, "evidence/p1_active_roster.json")
    raw, receipt = unpack(lock)
    source = lock["source_sha256"]
    ledger = read(main_sha, epoch_path(source))
    epoch = source[:16]
    status = read(archive_sha, f"{epoch}/archive_status.json")
    dirs = git("ls-tree", "-d", "--name-only", f"{archive_sha}:{epoch}").decode().splitlines()
    if any(re.fullmatch(r"shard_[0-9]{4}", name) is None for name in dirs):
        raise ValueError("unexpected directory in archive epoch")
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        roster = root / "mainboard.csv"
        roster.write_bytes(raw)
        plan = build_plan(roster, root / "shards", receipt["requested_day"])
        result = queue(plan, ledger, status, [int(name[6:]) for name in dirs])
    return {**result, "main_commit": main_sha, "archive_commit": archive_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--archive-sha", required=True)
    args = parser.parse_args()
    print(json.dumps(from_git(args.repo, args.main_sha, args.archive_sha), indent=2))


if __name__ == "__main__":
    main()
