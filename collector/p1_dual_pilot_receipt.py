"""Immutable, evidence-backed P1 dual-shard pilot receipts in GitHub main.

This research receipt is durable after short-lived Actions artifacts expire.
Never infers dual success from a green job, never certifies PIT, never trades.
"""
import argparse
import base64
import json
import os
from pathlib import Path

from collector.p1_checkpoint import gh, epoch_path

PILOT_CRON = "10 15 * * 1-5"


def build(selection, progress, policy, *, run_id, attempt, event, cron):
    if (type(run_id) is not int or run_id <= 0 or
            type(attempt) is not int or attempt <= 0 or
            event not in ("schedule", "workflow_dispatch") or
            (event == "schedule" and cron != PILOT_CRON) or
            (event == "workflow_dispatch" and cron not in ("", None))):
        raise ValueError("invalid pilot run identity or scheduled trigger")
    if (selection.get("trade_gate") != "BLOCKED"
            or selection.get("requested_shards") != 2
            or progress.get("phase") != "P1_READ_ONLY_RUN_PROGRESS"
            or progress.get("trade_gate") != "BLOCKED"
            or progress.get("historical_PIT_verified") is not False
            or progress.get("orders") != []
            or progress.get("executable_candidates") != []
            or progress.get("archive_csv_replay_enabled") is not True
            or progress.get("archive_gap_issuers") != 0
            or policy.get("phase") != "P1_OPTIONAL_SECOND_SHARD_POLICY"
            or policy.get("trade_gate") != "BLOCKED"
            or policy.get("historical_PIT_verified") is not False
            or policy.get("orders") != [] or policy.get("executable_candidates") != []):
        raise ValueError("pilot receipt lacks validated research-only evidence")
    epoch = progress.get("source_sha256")
    epoch_path(epoch)  # Require a literal SHA256 source epoch.
    selected = selection.get("selected_shards")
    if (not isinstance(selected, list)
            or not 1 <= len(selected) <= 2
            or any(type(i) is not int or not 0 <= i < 10000 for i in selected)
            or len(set(selected)) != len(selected)
            or selection.get("selected_count") != len(selected)
            or progress.get("selected_count") != len(selected)):
        raise ValueError("invalid selected pilot shards")
    actual = progress.get("new_selected_shards")
    n = progress.get("new_shards_durably_accepted")
    outcome = progress.get("dual_pilot_result")
    effective = policy.get("effective_shard_count")
    if (not isinstance(actual, list)
            or any(type(i) is not int for i in actual)
            or len(set(actual)) != len(actual)
            or not set(actual).issubset(selected)
            or type(n) is not int or n != len(actual)
            or n != progress.get("new_shard_count")
            or type(effective) is not int or effective not in (1, 2)
            or progress.get("effective_shard_count") != effective
            or policy.get("accepted_second") is not (effective == 2)
            or outcome not in ("TWO_VERIFIED_SHARDS_ARCHIVED",
                               "FIRST_ARCHIVED_SECOND_REJECTED",
                               "DUAL_PILOT_NOT_YET_PROVEN",
                               "ONLY_ONE_SHARD_PENDING")):
        raise ValueError("inconsistent durable dual pilot evidence")
    before = progress.get("previous_shards")
    after = progress.get("current_shards")
    if (type(before) is not int or before < 0
            or type(after) is not int or after != before + n
            or progress.get("status") !=
            ("DURABLE_PROGRESS" if n else "SUCCESS_NO_NEW_SHARD")):
        raise ValueError("pilot checkpoint delta is not durably proven")
    if outcome == "TWO_VERIFIED_SHARDS_ARCHIVED":
        if (len(selected) != 2 or set(actual) != set(selected) or n != 2
                or effective != 2 or policy.get("second_verification_passed") is not True
                or policy.get("status") != "SECOND_SHARD_VERIFIED"):
            raise ValueError("two-shard success is not independently proven")
    elif outcome == "FIRST_ARCHIVED_SECOND_REJECTED":
        if (len(selected) != 2 or actual != [selected[0]] or n != 1
                or effective != 1 or
                policy.get("status") not in (
                    "SECOND_FAILED_PRESERVE_FIRST", "SECOND_INVALID_PRESERVE_FIRST")):
            raise ValueError("unproven safe second-shard fallback")
    elif outcome == "ONLY_ONE_SHARD_PENDING":
        if len(selected) != 1 or effective != 1:
            raise ValueError("invalid final-shard special case")
    elif outcome == "DUAL_PILOT_NOT_YET_PROVEN" and n > 2:
        raise ValueError("invalid unproven pilot count")
    return {
        "phase": "P1_DURABLE_DUAL_SHARD_PILOT_RECEIPT",
        "source_sha256": epoch,
        "run_id": run_id,
        "run_attempt": attempt,
        "trigger": event,
        "trigger_cron_utc": cron if event == "schedule" else None,
        "requested_shards": 2,
        "selected_shards": selected,
        "new_selected_shards": actual,
        "new_shards_durably_accepted": n,
        "dual_pilot_result": outcome,
        "second_policy_status": policy.get("status"),
        "checkpoint_shards_before": before,
        "checkpoint_shards_after": progress.get("current_shards"),
        "archive_csv_replay_enabled": True,
        "archive_gap_issuers": 0,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def receipt_path(receipt):
    epoch_path(receipt["source_sha256"])
    run_id = receipt["run_id"]
    attempt = receipt["run_attempt"]
    if type(run_id) is not int or run_id <= 0 or type(attempt) is not int or attempt <= 0:
        raise ValueError("invalid durable pilot id")
    return (f"evidence/pilot_runs/{receipt['source_sha256'][:16]}/"
            f"run_{run_id}_attempt_{attempt}.json")


def persist(repo, receipt):
    """Create only; refuse to overwrite a different receipt for the same run."""
    if not isinstance(repo, str) or repo.count("/") != 1:
        raise ValueError("GitHub repository required")
    path = receipt_path(receipt)
    content = base64.b64encode(
        (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode()
    ).decode()
    body = {"message": "audit(p1): persist independently verified dual-shard pilot [NO TRADES]",
            "branch": "main", "content": content}
    # GitHub Contents PUT without a blob SHA is create-only; duplicate runs
    # should not overwrite evidence or silently replace prior verdicts.
    gh("-X", "PUT", f"repos/{repo}/contents/{path}",
       "--input", "-", input_data=json.dumps(body))
    # A successful request alone is insufficient: read the saved bytes back.
    response = json.loads(gh(f"repos/{repo}/contents/{path}", "-f", "ref=main",
                             "--method", "GET"))
    if not response.get("sha"):
        raise ValueError("pilot receipt missing remote blob SHA")
    saved = json.loads(base64.b64decode(response["content"]).decode())
    if saved != receipt:
        raise ValueError("persisted dual pilot differs from accepted local evidence")
    return path


def main():
    p = argparse.ArgumentParser()
    for key in ("selection", "progress", "policy", "out"):
        p.add_argument("--"+key, required=True)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    args = p.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    receipt = build(
        read(args.selection), read(args.progress), read(args.policy),
        run_id=int(os.environ["GITHUB_RUN_ID"]),
        attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        event=os.environ["GITHUB_EVENT_NAME"],
        cron=os.environ.get("P1_TRIGGER_CRON", ""),
    )
    path = persist(args.repo, receipt)
    report = dict(receipt, github_path=path, remote_readback_verified=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"dual_pilot_result": report["dual_pilot_result"],
                      "github_path": path, "remote_readback_verified": True,
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
