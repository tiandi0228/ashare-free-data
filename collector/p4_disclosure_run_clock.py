"""Cross-check a disclosure handoff's claimed observation against Actions metadata."""
from datetime import datetime, timezone
import re


def _instant(raw):
    if not isinstance(raw, str):
        raise ValueError("missing timestamp")
    stamp = datetime.fromisoformat(raw)
    if stamp.utcoffset() is None:
        raise ValueError("explicit timezone required")
    return stamp.astimezone(timezone.utc)


def verify(run, artifact, record, *, repo, run_id, attempt, head_sha):
    if (type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1
            or not isinstance(head_sha, str) or re.fullmatch(r"[0-9a-f]{40}", head_sha) is None):
        raise ValueError("invalid expected run identity")
    if (run.get("id"), run.get("run_attempt"), run.get("head_sha"), run.get("head_branch"),
            run.get("path"), run.get("status"), run.get("conclusion"),
            (run.get("repository") or {}).get("full_name")) != (
            run_id, attempt, head_sha, "main", ".github/workflows/p3-prospective-official-observation.yml",
            "completed", "success", repo):
        raise ValueError("unexpected disclosure run attempt")
    identity = artifact.get("workflow_run") or {}
    if (artifact.get("name") != f"p4-registered-disclosure-{run_id}-{attempt}"
            or artifact.get("expired") is not False
            or (identity.get("id"), identity.get("head_sha"), identity.get("head_branch"))
            != (run_id, head_sha, "main")):
        raise ValueError("artifact is not bound to the selected disclosure attempt")
    created = _instant(artifact.get("created_at"))
    started = _instant(run.get("run_started_at"))
    finished = _instant(run.get("updated_at"))
    observed = _instant(record.get("observed_at"))
    if not started <= observed <= created <= finished:
        raise ValueError("claimed observation is outside the run/artifact clock envelope")
    return {"run_id": run_id, "run_attempt": attempt, "artifact_id": artifact["id"],
            "run_started_at": started.isoformat(), "artifact_created_at": created.isoformat(),
            "observed_at": observed.isoformat(),
            "scope": "METADATA_CLOCK_CONSISTENCY_NOT_PROVIDER_OR_TRADE_ATTESTATION"}
