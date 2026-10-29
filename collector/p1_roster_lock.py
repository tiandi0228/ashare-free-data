"""Pin one original Baostock vendor roster for repeatable P1 research backfill.

The single immutable GitHub Contents record holds the original CSV bytes and
original unverified receipt. Pinned bytes are NEVER a fresh market observation,
official historical constituent list, or tradability certification. NO TRADES.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from collector.baostock_dated_universe import FIELDS
from collector.p1_roster_shard_manifest import CODE

LOCK_PATH = "evidence/p1_active_roster.json"
LOCK_PHASE = "P1_PINNED_VENDOR_ROSTER_RESEARCH_ONLY"


def check_source(raw, receipt):
    if not isinstance(raw, bytes) or not 10000 < len(raw) < 1000000:
        raise ValueError("invalid frozen roster byte size")
    if not isinstance(receipt, dict):
        raise ValueError("missing original vendor receipt")
    if receipt.get("status") not in (
        "OBSERVED_UNVERIFIED", "FROZEN_VENDOR_SNAPSHOT_UNVERIFIED"
    ):
        raise ValueError("unverified or incomplete original vendor receipt")
    if (receipt.get("trade_gate") != "BLOCKED"
            or receipt.get("orders") != []
            or receipt.get("executable_candidates") != []
            or receipt.get("historical_PIT_verified") is not False
            or receipt.get("publisher_authenticated") is not False
            or receipt.get("paid_api_calls") != 0):
        raise ValueError("unsafe vendor receipt")
    if receipt["status"] == "FROZEN_VENDOR_SNAPSHOT_UNVERIFIED":
        if (receipt.get("snapshot_reused") is not True
                or type(receipt.get("snapshot_origin_run")) is not int
                or receipt["snapshot_origin_run"] <= 0):
            raise ValueError("missing stale vendor origin")
    if (type(receipt.get("logical_queries")) is not int
            or not 1 <= receipt["logical_queries"] <= 2
            or type(receipt.get("mainboard_prefix_rows")) is not int
            or not 2500 <= receipt["mainboard_prefix_rows"] <= 6000):
        raise ValueError("invalid original vendor coverage")
    if hashlib.sha256(raw).hexdigest() != receipt.get("mainboard_sha256"):
        raise ValueError("original vendor CSV SHA mismatch")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""))
        if tuple(next(reader)) != FIELDS:
            raise ValueError("invalid roster CSV fields")
        rows = list(reader)
    except (UnicodeError, StopIteration, csv.Error) as exc:
        raise ValueError("invalid roster CSV encoding") from exc
    if len(rows) != receipt["mainboard_prefix_rows"]:
        raise ValueError("roster size differs from original receipt")
    seen = set()
    for row in rows:
        if (len(row) != len(FIELDS) or not CODE.fullmatch(row[0])
                or row[0] in seen or row[1] not in ("0", "1")
                or not row[2].strip()):
            raise ValueError("invalid or duplicate original issuer")
        seen.add(row[0])
    return hashlib.sha256(raw).hexdigest()


def pack(raw, receipt, run_id):
    digest = check_source(raw, receipt)
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("invalid originating run")
    return {
        "phase": LOCK_PHASE,
        "source_sha256": digest,
        "created_run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_requested_day": receipt["requested_day"],
        "original_quality": receipt,
        "original_csv_base64": base64.b64encode(raw).decode("ascii"),
        "historical_PIT_verified": False,
        "publisher_authenticated": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def unpack(lock):
    if not isinstance(lock, dict) or lock.get("phase") != LOCK_PHASE:
        raise ValueError("invalid pinned roster phase")
    if (lock.get("trade_gate") != "BLOCKED"
            or lock.get("orders") != [] or lock.get("executable_candidates") != []
            or lock.get("historical_PIT_verified") is not False
            or lock.get("publisher_authenticated") is not False
            or type(lock.get("created_run_id")) is not int
            or lock["created_run_id"] <= 0):
        raise ValueError("unsafe pinned roster metadata")
    try:
        raw = base64.b64decode(lock["original_csv_base64"], validate=True)
    except (ValueError, KeyError) as exc:
        raise ValueError("invalid pinned original CSV") from exc
    receipt = lock["original_quality"]
    digest = check_source(raw, receipt)
    if digest != lock.get("source_sha256") or receipt["requested_day"] != lock.get("source_requested_day"):
        raise ValueError("pinned source identity mismatch")
    return raw, receipt


def github_api(*args, input_data=None):
    return subprocess.run(
        ["gh", "api", *args], input=input_data, text=True,
        capture_output=True, check=True, timeout=45
    ).stdout


def remote_read(repo):
    try:
        result = json.loads(github_api(
            f"repos/{repo}/contents/{LOCK_PATH}",
            "-f", "ref=main", "--method", "GET"
        ))
    except subprocess.CalledProcessError as exc:
        if "404" in (exc.stderr or "") and "Not Found" in (exc.stderr or ""):
            return None
        raise
    raw = base64.b64decode(result["content"])
    lock = json.loads(raw.decode("utf-8"))
    unpack(lock)
    return lock


def remote_create(repo, lock):
    data = json.dumps(lock, ensure_ascii=False, sort_keys=True) + "\n"
    content = base64.b64encode(data.encode("utf-8")).decode("ascii")
    github_api(
        "-X", "PUT", f"repos/{repo}/contents/{LOCK_PATH}",
        "-f", "message=data(p1): pin immutable unverified vendor roster for research [NO TRADES]",
        "-f", f"content={content}", "-f", "branch=main"
    )


def materialize(lock, out, selection):
    raw, original = unpack(lock)
    path = Path(out)
    path.mkdir(parents=True, exist_ok=True)
    quality = dict(original)
    origin = (original["snapshot_origin_run"]
              if original["status"] == "FROZEN_VENDOR_SNAPSHOT_UNVERIFIED"
              else lock["created_run_id"])
    quality.update(
        status="FROZEN_VENDOR_SNAPSHOT_UNVERIFIED",
        snapshot_reused=True,
        snapshot_origin_run=origin,
        snapshot_requested_day=original["requested_day"],
        source_day_is_official_publication_proof=False,
        pinned_research_roster=True,
        pin_created_run_id=lock["created_run_id"],
        historical_PIT_verified=False,
        publisher_authenticated=False,
        trade_gate="BLOCKED",
        orders=[],
        executable_candidates=[],
    )
    (path / "mainboard.csv").write_bytes(raw)
    (path / "quality.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2) + "\n"
    )
    report = {
        "phase": LOCK_PHASE, "selection": selection,
        "source_sha256": lock["source_sha256"],
        "pinned_requested_day": original["requested_day"],
        "pinned_created_run_id": lock["created_run_id"],
        "trade_gate": "BLOCKED", "historical_PIT_verified": False,
    }
    (path / "p1_roster_lock.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def execute(mode, repo, out, run_id=None):
    lock = remote_read(repo)
    if lock is not None:
        return materialize(lock, out, "EXISTING_PIN"), True
    if mode == "read":
        return {"phase": LOCK_PHASE, "selection": "NO_PIN_YET", "trade_gate": "BLOCKED"}, False
    path = Path(out)
    quality = json.loads((path / "quality.json").read_text())
    raw = (path / "mainboard.csv").read_bytes()
    lock = pack(raw, quality, run_id)
    remote_create(repo, lock)  # create-only; GitHub rejects concurrent/changed locks
    return materialize(lock, out, "NEW_PIN"), True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("read", "pin"), required=True)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--out", default="evidence")
    p.add_argument("--github-output")
    a = p.parse_args()
    if not a.repo or "/" not in a.repo:
        raise ValueError("GitHub repository required")
    run_id = int(os.environ["GITHUB_RUN_ID"]) if a.mode == "pin" else None
    report, locked = execute(a.mode, a.repo, a.out, run_id)
    if a.github_output:
        with Path(a.github_output).open("a") as handle:
            handle.write(f"locked={str(locked).lower()}\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
