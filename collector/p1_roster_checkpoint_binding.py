"""Read-only binding of an observed vendor roster to exactly one P1 epoch.

The roster is not official PIT membership. Matching provenance lets a dashboard
show a coherent *research checkpoint*, never executable market coverage.
"""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import epoch_path, validate
from collector.p1_roster_lock import unpack


def bind(roster, epochs):
    base = {
        "phase": "P1_PINNED_ROSTER_CHECKPOINT_BINDING",
        "status": "BLOCKED_UNVERIFIED_ROSTER_BINDING",
        "roster_sha256": None,
        "matched_epoch": None,
        "completed_shards": None,
        "total_shards": None,
        "checkpoint_percent": None,
        "completed_issuers": None,
        "publisher_authenticated": False,
        "original_csv_bytes_reverified": False,
        "historical_PIT_verified": False,
        "full_market_bars_certified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    if not isinstance(roster, dict) or not isinstance(epochs, dict):
        raise ValueError("roster object and epoch mapping required")
    if (roster.get("phase") != "P1_PINNED_VENDOR_ROSTER_RESEARCH_ONLY"
            or roster.get("publisher_authenticated") is not False
            or roster.get("historical_PIT_verified") is not False
            or roster.get("trade_gate") != "BLOCKED"
            or roster.get("orders") != []
            or roster.get("executable_candidates") != []):
        raise ValueError("unsafe or unrecognized roster")
    quality = roster.get("original_quality")
    if (not isinstance(quality, dict)
            or quality.get("phase") != "P1_FRESH_VENDOR_ROSTER"
            or quality.get("status") != "FROZEN_VENDOR_SNAPSHOT_UNVERIFIED"
            or quality.get("publisher_authenticated") is not False
            or quality.get("trade_gate") != "BLOCKED"
            or quality.get("historical_PIT_verified") is not False
            or quality.get("orders") != []
            or quality.get("executable_candidates") != []
            or quality.get("paid_api_calls") != 0):
        raise ValueError("unsafe or unrecognized source quality")
    # Inspect the actual base64-encoded original CSV, not merely declared digests.
    # unpack validates bytes, UTF-8 CSV schema, issuer uniqueness, original
    # receipt SHA, count, safety fields, and source date provenance.
    raw, receipt = unpack(roster)
    sha = roster.get("source_sha256")
    epoch_path(sha)
    if quality.get("mainboard_sha256") != sha:
        raise ValueError("roster original quality SHA does not match pinned source")
    for key, ledger in epochs.items():
        epoch_path(key)
        validate(ledger)
        if ledger["source_sha256"] != key:
            raise ValueError("misfiled epoch checkpoint")
    result = dict(base, roster_sha256=sha, original_csv_bytes_reverified=True)
    if sha not in epochs:
        return dict(result, status="PINNED_EPOCH_CHECKPOINT_MISSING")
    ledger = epochs[sha]
    return dict(result,
                status="MATCHED_UNVERIFIED_RESEARCH_EPOCH",
                matched_epoch=sha,
                completed_shards=ledger["completed_shards"],
                total_shards=ledger["shard_count"],
                checkpoint_percent=round(100*ledger["completed_shards"]/ledger["shard_count"], 2),
                completed_issuers=ledger["completed_issuers"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", type=Path, default=Path("evidence/p1_active_roster.json"))
    ap.add_argument("--epochs", type=Path, default=Path("evidence/checkpoints"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    roster = json.loads(a.roster.read_text(encoding="utf-8"))
    epochs = {}
    for path in sorted(a.epochs.glob("*.json")):
        epoch_path(path.stem)
        epochs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    result = bind(roster, epochs)
    payload = json.dumps(result, ensure_ascii=False, indent=2)+"\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
