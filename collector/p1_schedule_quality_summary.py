"""Offline quality summary of immutable P1 scheduled run receipts (NO TRADES).

Only observed receipts are counted. Missing receipts cannot prove missing cron
fires; source in-flight receipts do not authenticate final Actions conclusions.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from collector.p1_schedule_run_provenance import (
    ALLOWED_CRONS, PHASE as RECEIPT_PHASE, delay_class, nominal, parse_utc,
)

EPOCH = re.compile(r"[a-f0-9]{16}\Z")
NAME = re.compile(r"run_([1-9][0-9]*)_attempt_([1-9][0-9]*)[.]json\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
HEAD = re.compile(r"[a-f0-9]{40}\Z")
MAX_RECEIPTS = 10000


def summarize(root, active_source_sha=None):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("source receipt root unavailable")
    if active_source_sha is not None and (
        not isinstance(active_source_sha, str) or not SHA.fullmatch(active_source_sha)
    ):
        raise ValueError("invalid active source epoch SHA")
    rows = []
    seen_run_ids = set()
    seen_nominal = set()
    paths = sorted(root.glob("*/run_*_attempt_*.json"))
    if len(paths) > MAX_RECEIPTS:
        raise ValueError("unbounded historical receipt count")
    for path in paths:
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("symlinked receipt forbidden")
        m = NAME.fullmatch(path.name)
        if not m or not EPOCH.fullmatch(path.parent.name):
            raise ValueError("unrecognized immutable receipt path")
        row = json.loads(path.read_text(encoding="utf-8"))
        rid, attempt = map(int, m.groups())
        sha = row.get("source_sha256") if isinstance(row, dict) else None
        cron = row.get("trigger_cron_utc")
        if (not isinstance(row, dict)
            or row.get("phase") != RECEIPT_PHASE
            or not isinstance(sha, str) or not SHA.fullmatch(sha)
            or sha[:16] != path.parent.name
            or row.get("run_id") != rid or row.get("run_attempt") != attempt
            or not isinstance(row.get("head_sha"), str)
            or not HEAD.fullmatch(row["head_sha"])
            or row.get("trigger") != "schedule"
            or cron not in ALLOWED_CRONS
            or row.get("trade_gate") != "BLOCKED"
            or row.get("orders") != []
            or row.get("historical_PIT_verified") is not False
            or row.get("github_workflow_conclusion_authenticated") is not False
            or row.get("actual_scheduled_execution_is_proven") is not True
            or type(row.get("per_shard_digests_from_locally_validated_ledger", False)) is not bool):
            raise ValueError("unsafe or unpinned P1 run receipt")
        if (rid, attempt) in seen_run_ids:
            raise ValueError("duplicated run identity across epochs")
        seen_run_ids.add((rid, attempt))
        created = parse_utc(row.get("github_run_created_at_utc"))
        scheduled, delay = nominal(cron, created)
        if (row.get("nominal_slot_utc") != scheduled.isoformat()
            or row.get("schedule_creation_delay_severity") != delay_class(delay)
            or type(row.get("github_queue_creation_delay_minutes")) not in (int, float)
            or abs(row["github_queue_creation_delay_minutes"] - delay) > 0.01):
            raise ValueError(f"unreconciled schedule attribution or lag at {path}: recorded={row.get('nominal_slot_utc')} vs calculated={scheduled.isoformat()}, severity={row.get('schedule_creation_delay_severity')} vs {delay_class(delay)}, minutes={row.get('github_queue_creation_delay_minutes')} vs {delay}")
        slot = (sha, scheduled.isoformat())
        if slot in seen_nominal:
            raise ValueError("duplicate epoch and nominal cron slot")
        seen_nominal.add(slot)
        n = row.get("shards_durably_accepted_by_run")
        before = row.get("checkpoint_shards_before")
        after = row.get("checkpoint_shards_after")
        indices = row.get("new_original_shard_indices")
        proofs = row.get("new_archived_shard_evidence")
        requested = row.get("requested_shards")
        if (type(n) is not int or not 0 <= n <= 2
            or type(requested) is not int or not 1 <= requested <= 2
            or n > requested
            or type(before) is not int or type(after) is not int
            or after-before != n
            or not isinstance(indices, list) or len(indices) != n
            or len(set(indices)) != n or any(type(i) is not int or i < 0 for i in indices)
            ):
            raise ValueError("run receipt shard delta invalid")
        sha_proven = row.get("per_shard_digests_from_locally_validated_ledger", False)
        if sha_proven:
            if (not isinstance(proofs, list) or len(proofs) != n
                or {x.get("index") for x in proofs if isinstance(x, dict)} != set(indices)
                or any(not isinstance(x, dict) or type(x.get("issuer_count")) is not int
                       or x["issuer_count"] < 1 or x["issuer_count"] > 8
                       or any(not isinstance(x.get(key), str)
                              or not SHA.fullmatch(x[key])
                              for key in ("manifest_sha256", "receipt_sha256"))
                       for x in proofs)):
                raise ValueError("invalid locally SHA-bound shard proofs")
        elif proofs is not None:
            raise ValueError("legacy receipt falsely claims local SHA proof")
        rows.append({"source_epoch_sha256": sha,
                     "run_id": rid, "attempt": attempt,
                     "nominal_slot_utc": scheduled.isoformat(),
                     "github_created_at_utc": created.isoformat(),
                     "queue_creation_delay_minutes": round(delay, 3),
                     "requested_shards": requested,
                     "locally_sha_ledger_accepted_shards": n if sha_proven else 0,
                     "legacy_shard_delta_without_local_SHA_proofs": n if not sha_proven else 0,
                     "new_original_shard_indices": sorted(indices)})
    if active_source_sha is not None:
        rows = [r for r in rows if r["source_epoch_sha256"] == active_source_sha]
    rows.sort(key=lambda x: (x["nominal_slot_utc"], x["run_id"], x["attempt"]))
    delays = [r["queue_creation_delay_minutes"] for r in rows]
    accepted = sum(r["locally_sha_ledger_accepted_shards"] for r in rows)
    return {
        "phase": "P1_OFFLINE_SCHEDULE_CREATION_LAG_AND_SHARD_EVIDENCE_SUMMARY",
        "status": "OBSERVED_RECEIPTS_ONLY_NOT_FULL_CRON_COVERAGE",
        "active_source_sha256": active_source_sha,
        "observed_receipts": len(rows),
        "locally_SHA_ledger_accepted_shards_across_observed_runs": accepted,
        "observed_runs_with_new_shards": sum(r["locally_sha_ledger_accepted_shards"] > 0 for r in rows),
        "legacy_receipt_runs_without_local_SHA_proofs": sum(
            r["legacy_shard_delta_without_local_SHA_proofs"] > 0 for r in rows),
        "legacy_reported_but_not_locally_SHA_proven_shard_deltas": sum(
            r["legacy_shard_delta_without_local_SHA_proofs"] for r in rows),
        "creation_delay_over_45m_count": sum(d > 45 for d in delays),
        "creation_delay_over_180m_count": sum(d > 180 for d in delays),
        "max_creation_delay_minutes": max(delays) if delays else None,
        "latest_observed_runs": list(reversed(rows[-10:])),
        "missing_cron_slots_inferred": False,
        "final_GitHub_workflow_conclusions_verified": False,
        "full_market_history_verified": False,
        "historical_PIT_verified": False,
        "automatic_dispatch_authorized": False,
        "writer_cutover_authorized": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--active-source-sha")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = summarize(a.root, a.active_source_sha)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in (
        "observed_receipts", "locally_SHA_ledger_accepted_shards_across_observed_runs",
        "creation_delay_over_45m_count", "creation_delay_over_180m_count",
        "max_creation_delay_minutes", "trade_gate")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
