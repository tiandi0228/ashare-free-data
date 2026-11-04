"""Independent post-conclusion P1 schedule evidence reconciliation (NO TRADES).

A source workflow may write a research-only receipt *before it exits*. This
module must authenticate final GitHub Actions success separately, and verify
that its SHA-linked same-epoch shard delta is present in the later durable
checkpoint. A missing source receipt is not a missed schedule or evidence of
success. Queue created_at is not actual runner start, and inferred nominal
schedule dates remain unverified.
"""
import argparse
import base64
import json
import re
from pathlib import Path

from collector.p1_checkpoint import epoch_path, gh, validate as validate_checkpoint
from collector.p1_schedule_run_provenance import (
    PHASE as SOURCE_PHASE, MAIN_PATH, DUAL_CRONS, TZ_CST, nominal, parse_utc
)

PHASE = "P1_SCHEDULE_FINAL_ACTIONS_AND_DURABLE_ARCHIVE_REVIEW"
HEX16 = re.compile(r"[0-9a-f]{16}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MAX_EPOCHS = 12


def base(state, run_id, reason=None):
    return {
        "phase": PHASE, "state": state, "run_id": run_id,
        "reason": reason, "trade_gate": "BLOCKED",
        "historical_PIT_verified": False,
        "orders": [], "executable_candidates": [],
        "buy_recommendations_authorized": False,
        "trade_authorized": False,
        "final_actions_success_authenticated": False,
        "scheduled_cron_origin_authenticated": False,
        "durable_same_epoch_shard_inclusion_verified": False,
    }


def verify(run, receipt=None, checkpoint=None):
    if (not isinstance(run, dict) or type(run.get("id")) is not int
            or run["id"] <= 0):
        raise ValueError("untrusted GitHub run identity")
    run_id = run["id"]
    if run.get("event") != "schedule":
        if run.get("event") in ("push", "workflow_dispatch", "pull_request"):
            return base("NOT_SCHEDULED_RUN", run_id)
        raise ValueError("unrecognized upstream run event")
    if (run.get("path") != MAIN_PATH or run.get("head_branch") != "main"
            or type(run.get("run_attempt")) is not int
            or run["run_attempt"] < 1
            or not isinstance(run.get("head_sha"), str)
            or not HEX40.fullmatch(run["head_sha"])):
        raise ValueError("incorrect upstream scheduled workflow or branch")
    if run.get("status") != "completed":
        return base("FINAL_ACTIONS_CONCLUSION_NOT_AVAILABLE", run_id)
    if run.get("conclusion") not in ("success", "failure", "cancelled",
                                      "timed_out", "skipped", "action_required",
                                      "neutral", "stale"):
        raise ValueError("unknown final GitHub Actions conclusion")
    if receipt is None:
        return base("SCHEDULE_RECEIPT_MISSING_NOT_PROVEN", run_id)
    if not isinstance(receipt, dict):
        raise ValueError("invalid scheduled source receipt")
    origin = receipt.get("source_sha256")
    epoch_path(origin)
    if (receipt.get("phase") != SOURCE_PHASE
            or receipt.get("run_id") != run_id
            or receipt.get("run_attempt") != run["run_attempt"]
            or receipt.get("head_sha") != run["head_sha"]
            or receipt.get("trigger") != "schedule"
            or receipt.get("trade_gate") != "BLOCKED"
            or receipt.get("historical_PIT_verified") is not False
            or receipt.get("orders") != []
            or receipt.get("executable_candidates") != []
            or receipt.get("trade_authorized") is not False
            or receipt.get("archive_csv_replay_enabled") is not True
            or receipt.get("github_workflow_conclusion_authenticated") is not False
            or receipt.get("runner_step_start_authenticated") is not False
            or receipt.get("nominal_slot_date_is_inferred_not_authenticated") is not True
            or receipt.get("actual_scheduled_execution_is_proven") is not True):
        raise ValueError("source receipt claims certification or wrong run identity")
    cron = receipt.get("trigger_cron_utc")
    created = parse_utc(run.get("created_at"))
    planned, delay = nominal(cron, created)
    requested = 2 if cron in DUAL_CRONS else 1
    if (receipt.get("requested_shards") != requested
            or receipt.get("github_run_created_at_utc") != created.isoformat()
            or receipt.get("nominal_slot_utc") != planned.isoformat()
            or receipt.get("nominal_slot_beijing") != planned.astimezone(TZ_CST).isoformat()
            or type(receipt.get("github_queue_creation_delay_minutes")) not in (int, float)
            or receipt["github_queue_creation_delay_minutes"] != delay
            or receipt.get("delay_exceeds_45_minutes") is not (delay > 45)):
        raise ValueError("literal cron, scheduled creation or delay contradiction")
    indices = receipt.get("new_original_shard_indices")
    before = receipt.get("checkpoint_shards_before")
    after = receipt.get("checkpoint_shards_after")
    accepted = receipt.get("shards_durably_accepted_by_run")
    if (not isinstance(indices, list)
            or any(type(x) is not int or x < 0 for x in indices)
            or len(set(indices)) != len(indices)
            or sorted(indices) != indices
            or type(accepted) is not int or not 0 <= accepted <= requested
            or type(before) is not int or before < 0
            or type(after) is not int or after != before + accepted
            or len(indices) != accepted):
        raise ValueError("shard delta not internally consistent")
    if checkpoint is None:
        return dict(base("PERMANENT_CHECKPOINT_UNAVAILABLE_NO_CERTIFICATION", run_id),
                    literal_cron_utc=cron)
    validate_checkpoint(checkpoint)
    if (checkpoint["source_sha256"] != origin
            or checkpoint["completed_shards"] < after
            or any(i >= checkpoint["shard_count"] for i in indices)):
        raise ValueError("remote permanent checkpoint contradicts source epoch")
    existing = {x["index"] for x in checkpoint["completed"]}
    if not set(indices).issubset(existing):
        raise ValueError("shard accepted by source not present in durable checkpoint")
    confirmed = run.get("conclusion") == "success"
    state = ("SCHEDULE_SUCCESS_AND_DURABLE_SHARDS_CONFIRMED"
             if confirmed and accepted > 0
             else "SCHEDULE_SUCCESS_NO_NEW_ARCHIVED_SHARDS"
             if confirmed else "SCHEDULE_FINAL_FAILURE_OR_OTHER_CONCLUSION")
    return dict(base(state, run_id),
                literal_cron_utc=cron,
                inferred_nominal_slot_beijing=planned.astimezone(TZ_CST).isoformat(),
                github_created_at_utc=created.isoformat(),
                github_creation_delay_minutes=delay,
                actual_runner_start_verified=False,
                github_final_conclusion=run["conclusion"],
                final_actions_success_authenticated=confirmed,
                scheduled_cron_origin_authenticated=True,
                durable_same_epoch_shard_inclusion_verified=True,
                source_sha256=origin,
                source_checkpoint_before=before,
                source_checkpoint_after=after,
                durable_checkpoint_current=checkpoint["completed_shards"],
                accepted_source_shard_indices=indices,
                durably_accepted_shards_in_source_run=accepted,
                inferred_nominal_slot_date_authenticated=False,
                limitations=[
                    "INFERRED_SLOT_DATE_NOT_GITHUB_ATTESTED",
                    "CREATED_AT_IS_QUEUE_CREATION_NOT_RUNNER_START",
                    "ORIGINAL_PRICE_BARS_NOT_HISTORICAL_PIT_CERTIFIED",
                    "RESEARCH_ONLY_NO_ORDERS_NO_BUY_SIGNALS",
                ])


def read_contents(repo, path):
    obj = json.loads(gh(f"repos/{repo}/contents/{path}",
                        "-f", "ref=main", "--method", "GET"))
    if (not isinstance(obj, dict) or obj.get("path") != path
            or obj.get("type") != "file" or not obj.get("sha")):
        raise ValueError("untrusted GitHub contents path")
    return json.loads(base64.b64decode(obj["content"]).decode())


def locate_schedule_receipt(repo, run_id, attempt):
    """Bound all source epochs; never infer absence from partial listing."""
    directory = "evidence/schedule_runs"
    try:
        folders = json.loads(gh(f"repos/{repo}/contents/{directory}",
                                "-f", "ref=main", "--method", "GET"))
    except Exception as exc:
        # A fresh project may have no schedule receipt folder; only a
        # verified GitHub 404 can establish this rather than an API failure.
        if getattr(exc, "returncode", None) == 1 and "404" in (getattr(exc, "stderr", "") or ""):
            return None
        raise
    if not isinstance(folders, list) or len(folders) > MAX_EPOCHS:
        raise ValueError("unbounded or invalid source epoch listing")
    found = []
    for item in folders:
        if not isinstance(item, dict) or item.get("type") != "dir":
            raise ValueError("invalid source epoch folder")
        prefix = item.get("name")
        if (not isinstance(prefix, str) or not HEX16.fullmatch(prefix)
                or item.get("path") != directory+"/"+prefix):
            raise ValueError("invalid source epoch path")
        path = f"{directory}/{prefix}/run_{run_id}_attempt_{attempt}.json"
        try:
            record = read_contents(repo, path)
        except Exception as exc:
            if getattr(exc, "returncode", None) == 1 and "404" in (getattr(exc, "stderr", "") or ""):
                continue
            raise
        if not isinstance(record, dict):
            raise ValueError("invalid source receipt JSON")
        epoch = record.get("source_sha256")
        epoch_path(epoch)
        if epoch[:16] != prefix:
            raise ValueError("source receipt stored under contradictory epoch")
        found.append(record)
    if len(found) > 1:
        raise ValueError("ambiguous scheduled receipt in multiple epochs")
    return found[0] if found else None


def run_review(repo, run_id):
    if (not isinstance(repo, str) or not REPO.fullmatch(repo)
            or type(run_id) is not int or run_id < 1):
        raise ValueError("untrusted run request")
    run = json.loads(gh(f"repos/{repo}/actions/runs/{run_id}"))
    if not isinstance(run, dict) or run.get("id") != run_id:
        raise ValueError("GitHub Actions run id mismatch")
    if run.get("event") != "schedule" or run.get("status") != "completed":
        return verify(run)
    receipt = locate_schedule_receipt(repo, run_id, run.get("run_attempt"))
    if receipt is None:
        return verify(run)
    checkpoint = read_contents(repo, epoch_path(receipt.get("source_sha256")))
    return verify(run, receipt, checkpoint)


def latest_completed_schedule_run_id(repo):
    """Bounded source-workflow history only, not generic repository run list."""
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise ValueError("invalid repository")
    raw = gh(
        f"repos/{repo}/actions/workflows/p1-fresh-vendor-roster.yml/runs",
        "-f", "event=schedule", "-f", "per_page=25",
        "--method", "GET"
    )
    page = json.loads(raw)
    runs = page.get("workflow_runs") if isinstance(page, dict) else None
    if (not isinstance(runs, list) or len(runs) > 25
            or type(page.get("total_count")) is not int
            or page["total_count"] < len(runs)):
        raise ValueError("incomplete or invalid bounded P1 run history")
    completed = []
    for row in runs:
        if (not isinstance(row, dict)
                or type(row.get("id")) is not int or row["id"] <= 0
                or row.get("path") != MAIN_PATH
                or row.get("event") != "schedule"
                or row.get("head_branch") != "main"):
            raise ValueError("non-P1 entry in filtered scheduled run history")
        if row.get("status") == "completed":
            completed.append(row["id"])
    return max(completed) if completed else None


def main():
    p = argparse.ArgumentParser()
    import os
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--run-id", type=int)
    choice.add_argument("--latest-scheduled", action="store_true")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    run_id = args.run_id
    try:
        if args.latest_scheduled:
            run_id = latest_completed_schedule_run_id(args.repo)
        result = (run_review(args.repo, run_id)
                  if run_id is not None else
                  base("NO_COMPLETED_SCHEDULE_IN_BOUNDED_HISTORY", None))
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
        # An invalid source/remote response cannot certify a successful run.
        result = base("REJECTED_UNVERIFIED_SOURCE_OR_API", run_id,
                      type(exc).__name__)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False))
    if result["state"] == "REJECTED_UNVERIFIED_SOURCE_OR_API":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
