"""Cross-check a disclosure handoff's claimed observation against Actions metadata."""
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from zipfile import ZipFile, BadZipFile
import re


def _instant(raw):
    if not isinstance(raw, str):
        raise ValueError("missing timestamp")
    stamp = datetime.fromisoformat(raw)
    if stamp.utcoffset() is None:
        raise ValueError("explicit timezone required")
    return stamp.astimezone(timezone.utc)


RECEIPT_FILE = "p4_registered_daily_receipt.json"
HANDOFF_FILE = "p3_to_p4_readiness.json"
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024


def read_bound_zip(artifact, raw):
    """Verify the exact ZIP before parsing its two expected source members."""
    digest = artifact.get("digest")
    size = artifact.get("size_in_bytes")
    if (not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
            or type(size) is not int or not 0 < size <= MAX_ARTIFACT_BYTES):
        raise ValueError("missing or invalid Actions artifact digest or size")
    if len(raw) != size or "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("downloaded artifact differs from Actions digest or size")
    try:
        with ZipFile(BytesIO(raw)) as bundle:
            members = bundle.infolist()
            if (len(members) != 2 or {m.filename for m in members} != {RECEIPT_FILE, HANDOFF_FILE}
                    or any(m.is_dir() or not 0 < m.file_size <= MAX_ARTIFACT_BYTES for m in members)):
                raise ValueError("unexpected disclosure ZIP members")
            record = json.loads(bundle.read(RECEIPT_FILE))
            if not isinstance(record, dict):
                raise ValueError("unexpected disclosure receipt JSON")
            return record, bundle.read(HANDOFF_FILE)
    except BadZipFile as exc:
        raise ValueError("invalid disclosure ZIP") from exc


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
    if (type(artifact.get("id")) is not int or artifact["id"] < 1
            or artifact.get("name") != f"p4-registered-disclosure-{run_id}-{attempt}"
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
