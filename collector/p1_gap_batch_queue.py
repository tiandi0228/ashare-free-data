"""Build a pinned, read-only queue of at most two P1 shards per dispatch."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from collector.p1_archive_audit import audit
from collector.p1_checkpoint import epoch_path
from collector.p1_fresh_shard_plan import plan as build_plan
from collector.p1_gap_probe_fingerprint import PROBE_JSON_SHA256, PROBE_RUN_ID
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


def tracked_states(plan, pending, manifests, tracked, probe_raw):
    """Label shards against the validated snapshot and one exact historical probe."""
    if (not tracked or len(tracked) != len(set(tracked))
            or any(type(i) is not int or not 0 <= i < plan["shard_count"] for i in tracked)):
        raise ValueError("invalid tracked shard set")
    if hashlib.sha256(probe_raw).hexdigest() != PROBE_JSON_SHA256:
        raise ValueError("unexpected historical probe bytes")
    probe = json.loads(probe_raw)
    verified = {}
    for row in probe["verified"]:
        index = row["index"]
        shard = plan["shards"][index]
        codes = (manifests / shard["name"]).read_text().splitlines()
        if (row["manifest_sha256"] != shard["sha256"] or row["issuers"] != shard["count"]
                or set(row["csv_sha256_by_issuer"]) != set(codes)):
            raise ValueError("historical probe and frozen roster disagree")
        verified[index] = PROBE_RUN_ID
    pending = set(pending)
    return [
        dict(index=i, status=("ARCHIVED_IN_PINNED_SNAPSHOT" if i not in pending
                              else "PREPROBED_NOT_ARCHIVED" if i in verified
                              else "PENDING_NO_MATCH_IN_PINNED_PROBE"),
             historical_probe_run_id=verified.get(i))
        for i in tracked
    ]


def refresh_preview(report, requested, expected_epoch):
    """Narrow a saved selection against a newly verified read-only snapshot."""
    if (report["source_sha256"] != expected_epoch
            or report["archive_original_csvs_replayed"] is not True
            or report["archive_index_parity_checked"] is not True
            or report["trade_gate"] != "BLOCKED"):
        raise ValueError("fresh same-epoch original archive replay is required")
    if (not 1 <= len(requested) <= 2
            or any(type(i) is not int or not 0 <= i < report["total_shards"] for i in requested)
            or len(set(requested)) != len(requested)):
        raise ValueError("expected one or two distinct requested shards")
    pending = {index for batch in report["batches"] for index in batch["shard_indices"]}
    if len(pending) != report["pending_shards"]:
        raise ValueError("pending shard count disagrees with the checked queue")
    remaining = sorted(set(requested) & pending)
    skipped = sorted(set(requested) - pending)
    window = None
    if remaining:
        # A broad interval could silently select a different pending shard.
        within = sorted(i for i in pending if remaining[0] <= i <= remaining[-1])
        if within == remaining:
            window = {"gap_window": f"{remaining[0]}:{remaining[-1]}", "shards_per_run": str(len(remaining))}
    return dict(
        requested_shards=sorted(requested), already_archived_shards=skipped, remaining_shards=remaining,
        dispatch_preview=window, requires_separate_windows=bool(remaining and window is None),
        recheck_required_before_dispatch=True, dispatch_performed=False,
    )


def from_git(repo, main_sha, archive_sha, *, replay_checkout=None, tracked=(), probe_raw=None):
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
        if tracked:
            if probe_raw is None:
                raise ValueError("tracked states require the pinned probe fixture")
            result["tracked_shards"] = tracked_states(plan, ledger["pending_shards"], root / "shards",
                                                      tracked, probe_raw)
        if replay_checkout is not None:
            actual = subprocess.check_output(
                ["git", "-C", str(replay_checkout), "rev-parse", "HEAD"], timeout=30
            ).decode().strip()
            if actual != archive_sha:
                raise ValueError("archive replay checkout does not match pinned archive SHA")
            replayed = audit(plan, ledger, replay_checkout, replay=True)
            if (not replayed["archive_complete"] or replayed["repair_shard_count"] != 0
                    or replayed["archived_issuers"] != ledger["completed_issuers"]):
                raise ValueError("original archive replay and checkpoint do not reconcile")
            result.update(archive_original_csvs_replayed=True, archive_replay=replayed)
    return {**result, "main_commit": main_sha, "archive_commit": archive_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--archive-sha", required=True)
    parser.add_argument("--replay-checkout", type=Path,
                        help="Read-only archive checkout for independent original CSV replay")
    parser.add_argument("--track", type=int, nargs="+", default=[])
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--refresh-selection", type=int, nargs="+")
    parser.add_argument("--expected-epoch")
    args = parser.parse_args()
    report = from_git(args.repo, args.main_sha, args.archive_sha,
                      replay_checkout=args.replay_checkout, tracked=args.track,
                      probe_raw=args.probe.read_bytes() if args.probe else None)
    if args.refresh_selection is not None:
        report["refreshed_selection"] = refresh_preview(report, args.refresh_selection, args.expected_epoch)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
