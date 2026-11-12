"""Fresh, read-only GitHub preflight for explicitly manual P1 gap collection.

Re-read main checkpoint and archival branch metadata immediately before a
provider request and again before archival staging. No remote writes or trades.
"""
import argparse
import base64
import json
import os
import re
import subprocess
from pathlib import Path

from collector.p1_checkpoint import epoch_path
from collector.p1_prewrite_gap_guard import check

REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def decode_contents(envelope):
    if not isinstance(envelope, dict):
        raise ValueError("unexpected GitHub contents envelope")
    encoded = envelope.get("content")
    if envelope.get("encoding") != "base64" or not isinstance(encoded, str):
        raise ValueError("unverified GitHub contents encoding")
    raw = base64.b64decode("".join(encoded.split()), validate=True)
    return json.loads(raw.decode("utf-8"))


def read_remote(repo, path, ref):
    if (not isinstance(repo, str) or REPO.fullmatch(repo) is None
        or not isinstance(path, str) or not path or
        not isinstance(ref, str) or ref not in ("main", "research-csv-archive")):
        raise ValueError("unsafe GitHub read address")
    proc = subprocess.run(
        ["gh", "api", "--method", "GET", f"repos/{repo}/contents/{path}",
         "-f", f"ref={ref}"],
        capture_output=True, text=True, check=False, timeout=45)
    if proc.returncode:
        raise ValueError("remote GitHub read failed (no raw output disclosed)")
    return decode_contents(json.loads(proc.stdout))


def verify(plan, selected_receipt, prior_ledger, repo, fetch=read_remote):
    if not isinstance(plan, dict):
        raise ValueError("missing P1 plan")
    if (not isinstance(selected_receipt, dict) or
        selected_receipt.get("phase") != "P1_BOUNDED_PILOT_SELECTION" or
        selected_receipt.get("trade_gate") != "BLOCKED" or
        selected_receipt.get("orders") != [] or
        type(selected_receipt.get("requested_shards")) is not int or
        selected_receipt["requested_shards"] not in (1, 2)):
        raise ValueError("unsafe or missing pilot selection")
    selected = selected_receipt.get("selected_shards")
    if (not isinstance(selected, list) or
        len(selected) != selected_receipt.get("selected_count") or
        len(selected) > selected_receipt["requested_shards"]):
        raise ValueError("pilot selection count mismatch")
    source = plan.get("source_sha256")
    current = fetch(repo, epoch_path(source), "main")
    archived = fetch(repo, f"{source[:16]}/archive_status.json", "research-csv-archive")
    result = check(plan, selected, prior_ledger, current, archived)
    if result["permission_to_write_or_trade"] is not False:
        raise ValueError("preflight unexpectedly authorized writes")
    return {
        **result,
        "remote_main_checkpoint_read_in_this_attempt": True,
        "remote_archive_status_read_in_this_attempt": True,
        "authorized_action": "RESEARCH_READ_ONLY_PREFLIGHT",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--selection", required=True, type=Path)
    p.add_argument("--prior", required=True, type=Path)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    read = lambda file: json.loads(file.read_text(encoding="utf-8"))
    result = verify(read(a.plan), read(a.selection), read(a.prior), a.repo)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "phase": result["phase"], "status": result["status"],
        "selected_missing_shards": result["selected_missing_shards"],
        "trade_gate": result["trade_gate"],
        "permission_to_write_or_trade": result["permission_to_write_or_trade"],
    }))


if __name__ == "__main__":
    main()
