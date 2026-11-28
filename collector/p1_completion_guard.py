"""Research-only P1 completion guard: no vendor queries after a verified 400/400 archive.

Read two exact Git commits; inconsistencies fail closed instead of appearing complete.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

from collector.p1_checkpoint import epoch_path, validate


def decision(checkpoint, archive_status, lock):
    validate(checkpoint)
    epoch = checkpoint["source_sha256"]
    if (lock.get("source_sha256") != epoch or
            archive_status.get("source_sha256") != epoch or
            archive_status.get("trade_gate") != "BLOCKED"):
        raise ValueError("P1 guard epoch or no-trade mismatch")
    archive = archive_status.get("archived_shards")
    if (not isinstance(archive, list) or
            any(type(i) is not int for i in archive) or
            len(archive) != len(set(archive))):
        raise ValueError("P1 guard invalid archive index")
    completed = {row["index"] for row in checkpoint["completed"]}
    if set(archive) != completed or len(archive) != checkpoint["completed_shards"]:
        raise ValueError("P1 guard archive/checkpoint mismatch")
    if checkpoint["shard_count"] != 400:
        raise ValueError("P1 guard unexpected frozen roster geometry")
    pending = checkpoint["pending_shards"]
    if len(pending) + len(archive) != 400:
        raise ValueError("P1 guard incomplete accounting")
    finished = len(archive) == 400 and pending == []
    if finished and completed != set(range(400)):
        raise ValueError("P1 guard non-contiguous completed roster")
    return {
        "phase": "P1_COMPLETION_GUARD_RESEARCH_ONLY",
        "archived_shards": len(archive),
        "total_shards": 400,
        "pending_shards": pending,
        "should_collect": not finished,
        "status": "FULL_ARCHIVE_SKIP_VENDOR" if finished else "PENDING_ALLOW_BOUNDED_VENDOR",
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "permission_to_trade": False,
    }


def run(repo, main_sha, archive_sha):
    for sha in (main_sha, archive_sha):
        if not isinstance(sha, str) or re.fullmatch(r"[a-f0-9]{40}", sha) is None:
            raise ValueError("P1 guard requires exact Git commit IDs")

    def read(sha, path):
        raw = subprocess.check_output(["git", "-C", str(repo), "show", f"{sha}:{path}"], timeout=25)
        return json.loads(raw)

    lock = read(main_sha, "evidence/p1_active_roster.json")
    epoch = lock.get("source_sha256")
    checkpoint = read(main_sha, epoch_path(epoch))
    archive = read(archive_sha, epoch[:16] + "/archive_status.json")
    return {**decision(checkpoint, archive, lock), "main_commit": main_sha,
            "archive_commit": archive_sha}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--main-sha", required=True)
    p.add_argument("--archive-sha", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    report = run(a.repo, a.main_sha, a.archive_sha)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write("collect=" + str(report["should_collect"]).lower() + "\n")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(f"### P1 completion guard: {report['status']}\n"
                    f"- Actual archive: {report['archived_shards']}/400\n"
                    f"- Remaining: {report['pending_shards']}\n"
                    "- Trade gate: BLOCKED; not an official/PIT certification\n")
    print(json.dumps({"phase": report["phase"], "status": report["status"],
                      "count": report["archived_shards"], "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
