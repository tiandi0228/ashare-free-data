"""Exact P1 scheduled-cron provenance from GitHub run identity (NO TRADES).

GitHub Actions creates scheduled jobs on a best-effort basis: a job created
late must NOT be attributed to whichever different cron is nearest. Bind the
literal trusted schedule event to its nominal UTC day and record launch delay.
The run is still in progress when this receipt is persisted; archive evidence
is independent of final workflow conclusion and does not certify PIT or trades.
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
from pathlib import Path

from collector.p1_checkpoint import epoch_path, gh

UTC = dt.timezone.utc
TZ_CST = dt.timezone(dt.timedelta(hours=8))
PHASE = "P1_EXACT_SCHEDULE_PROVENANCE_PENDING_ACTIONS_CONCLUSION"
MAIN_PATH = ".github/workflows/p1-fresh-vendor-roster.yml"
DUAL_HOURS = frozenset((3, 5, 7, 9, 11, 15))
WEEKDAY_HOURS = frozenset((0, 1, 3, 5, 7, 9, 11, 13, 15))
WEEKEND_HOURS = frozenset((1, 7, 11, 15))
# An additional early Monday-Friday Beijing 01:10 cron uses Sunday-Thursday
# at 17:10 UTC. Do not confuse that UTC day with the local trading day.
ALLOWED_CRONS = {
    **{f"10 {hour} * * 1-5": (hour, frozenset(range(1, 6)))
       for hour in WEEKDAY_HOURS},
    "10 17 * * 0-4": (17, frozenset((0, 1, 2, 3, 4))),
    **{f"10 {hour} * * 6,0": (hour, frozenset((6, 0)))
       for hour in WEEKEND_HOURS},
}
DUAL_CRONS = frozenset(f"10 {hour} * * 1-5" for hour in DUAL_HOURS)
SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN_FILE = re.compile(r"[1-9][0-9]*\Z")


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("missing GitHub timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("GitHub timestamp without timezone")
    return parsed.astimezone(UTC)


def nominal(cron, created):
    if cron not in ALLOWED_CRONS:
        raise ValueError("cron not in audited P1 schedule")
    hour, days = ALLOWED_CRONS[cron]
    # Python weekday: Monday=0...Sunday=6; cron weekday: Sunday=0.
    for distance in range(2):
        day = (created - dt.timedelta(days=distance)).date()
        cron_weekday = (day.weekday()+1) % 7
        proposed = dt.datetime.combine(day, dt.time(hour, 10), UTC)
        if cron_weekday in days and proposed <= created + dt.timedelta(minutes=2):
            lag = (created - proposed).total_seconds()/60
            if lag < -2 or lag > 24*60:
                raise ValueError("schedule creation outside source attribution window")
            return proposed, round(lag, 3)
    # A delayed or malformed GitHub event is unassignable; do not guess
    # a day or classify this as proof of another slot succeeding.
    raise ValueError("cannot match declared cron to same or previous UTC day")


def build(run, progress, *, cron, run_id, attempt, sha):
    if (not isinstance(run, dict) or type(run_id) is not int or run_id < 1
            or type(attempt) is not int or attempt < 1
            or not isinstance(sha, str) or not SHA.fullmatch(sha)
            or run.get("id") != run_id or run.get("run_attempt") != attempt
            or run.get("head_sha") != sha
            or run.get("event") != "schedule"
            or run.get("path") != MAIN_PATH
            or run.get("head_branch") != "main"
            or run.get("status") not in ("queued", "in_progress", "completed")
            or not isinstance(progress, dict)):
        raise ValueError("run identity or main-branch provenance not authenticated")
    created = parse_utc(run.get("created_at"))
    planned, delay = nominal(cron, created)
    expected_shards = 2 if cron in DUAL_CRONS else 1
    source = progress.get("source_sha256")
    epoch_path(source)
    before = progress.get("previous_shards")
    after = progress.get("current_shards")
    accepted = progress.get("new_shards_durably_accepted")
    selected = progress.get("new_selected_shards")
    if (progress.get("phase") != "P1_READ_ONLY_RUN_PROGRESS"
            or progress.get("status") not in ("DURABLE_PROGRESS", "SUCCESS_NO_NEW_SHARD")
            or progress.get("trade_gate") != "BLOCKED"
            or progress.get("historical_PIT_verified") is not False
            or progress.get("orders") != []
            or progress.get("executable_candidates") != []
            or progress.get("archive_csv_replay_enabled") is not True
            or progress.get("archive_gap_issuers") != 0
            or type(before) is not int or before < 0
            or type(after) is not int or after < before
            or type(accepted) is not int or not 0 <= accepted <= expected_shards
            or not isinstance(selected, list)
            or any(type(x) is not int or x < 0 for x in selected)
            or len(set(selected)) != len(selected)
            or len(selected) != accepted
            or after - before != accepted
            or progress.get("new_shard_count") != accepted
            or progress.get("effective_shard_count") not in (1, 2)
            or progress.get("effective_shard_count") > expected_shards):
        raise ValueError("research checkpoint growth or trade gate not proven")
    return {
        "phase": PHASE,
        "run_id": run_id,
        "run_attempt": attempt,
        "head_sha": sha,
        "source_sha256": source,
        "trigger": "schedule",
        "trigger_cron_utc": cron,
        "requested_shards": expected_shards,
        "nominal_slot_utc": planned.isoformat(),
        "nominal_slot_beijing": planned.astimezone(TZ_CST).isoformat(),
        "github_run_created_at_utc": created.isoformat(),
        "github_queue_creation_delay_minutes": delay,
        "delay_exceeds_45_minutes": delay > 45,
        "runner_step_start_authenticated": False,
        "github_workflow_conclusion_authenticated": False,
        "actual_scheduled_execution_is_proven": True,
        "shards_durably_accepted_by_run": accepted,
        "checkpoint_shards_before": before,
        "checkpoint_shards_after": after,
        "new_original_shard_indices": sorted(selected),
        "archive_csv_replay_enabled": True,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "trade_authorized": False,
        "limitations": [
            "GITHUB_RUN_CREATED_AT_IS_QUEUE_CREATION_NOT_RUNNER_STEP_START",
            "LITERAL_EVENT_CRON_DOES_NOT_PROVE_FUTURE_SCHEDULE_RELIABILITY",
            "IN_FLIGHT_SOURCE_RECEIPT_NOT_FINAL_ACTIONS_SUCCESS_ATTESTATION",
            "SOURCE_BARS_NOT_HISTORICAL_PIT_OR_TRADING_ELIGIBILITY",
        ],
    }


def path_for(record):
    epoch_path(record["source_sha256"])
    run, attempt = record.get("run_id"), record.get("run_attempt")
    if type(run) is not int or run <= 0 or type(attempt) is not int or attempt <= 0:
        raise ValueError("invalid exact schedule run identity")
    return (f"evidence/schedule_runs/{record['source_sha256'][:16]}/"
            f"run_{run}_attempt_{attempt}.json")


def persist(repo, record):
    """Create-only source receipt; never silently replace an earlier run."""
    if (not isinstance(repo, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)):
        raise ValueError("invalid GitHub repository")
    path = path_for(record)
    original = (json.dumps(record, sort_keys=True, ensure_ascii=False,
                           indent=2)+"\n").encode()
    payload = {
        "branch": "main",
        "message": "audit(p1): save exact scheduled source run provenance [NO TRADES]",
        "content": base64.b64encode(original).decode(),
    }
    gh("-X", "PUT", f"repos/{repo}/contents/{path}", "--input", "-",
       input_data=json.dumps(payload))
    remote = json.loads(gh(f"repos/{repo}/contents/{path}", "-f",
                           "ref=main", "--method", "GET"))
    if (remote.get("path") != path or not remote.get("sha")
            or base64.b64decode(remote.get("content", "")) != original):
        raise ValueError("published schedule receipt readback mismatch")
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--progress", required=True)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    args = p.parse_args()
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        raise ValueError("no attribution of manual or push event to a schedule")
    run_id = int(os.environ["GITHUB_RUN_ID"])
    # Read GitHub's own run JSON rather than synthesizing a run identity.
    remote = json.loads(gh(f"repos/{args.repo}/actions/runs/{run_id}"))
    result = build(
        remote,
        json.loads(Path(args.progress).read_text()),
        cron=os.environ["P1_TRIGGER_CRON"],
        run_id=run_id,
        attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
        sha=os.environ["GITHUB_SHA"],
    )
    location = persist(args.repo, result)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(dict(result, github_path=location,
                                    remote_readback_verified=True),
                               ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({
        "schedule_cron": result["trigger_cron_utc"],
        "nominal_beijing": result["nominal_slot_beijing"],
        "github_queue_creation_delay_minutes":
            result["github_queue_creation_delay_minutes"],
        "durably_accepted_shards": result["shards_durably_accepted_by_run"],
        "receipt": location,
        "trade_gate": "BLOCKED",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
