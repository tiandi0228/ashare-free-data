"""Recover archived P1 shards after a crash between Git archive and checkpoint.

Archive-to-main persistence is not atomic. Only replay the same frozen roster's
immutable archived CSV and receipt before adding an orphan shard to the
checkpoint. Never count unverified archive markers or change the trade gate.
"""
import argparse
import json
from pathlib import Path

from collector.p1_checkpoint import validate as validate_checkpoint
from collector.p1_quad_verify import verify
from collector.p1_shard_ledger import reconcile

MAX_ORPHAN_REPLAY = 4


def recover(plan, prior, archive_root, manifest_root):
    if (plan.get("phase") != "P1_FRESH_VENDOR_SHARD_PLAN"
            or plan.get("trade_gate") != "BLOCKED"
            or plan.get("historical_PIT_verified") is not False
            or type(plan.get("shard_count")) is not int
            or plan["shard_count"] <= 0
            or not isinstance(plan.get("shards"), list)
            or len(plan["shards"]) != plan["shard_count"]):
        raise ValueError("unsafe frozen P1 recovery plan")
    if prior is not None:
        validate_checkpoint(prior)
        if (prior["source_sha256"] != plan["source_sha256"]
                or prior["shard_count"] != plan["shard_count"]):
            raise ValueError("cross-epoch orphan archive recovery forbidden")
        old = {item["index"] for item in prior["completed"]}
    else:
        old = set()
    epoch = Path(archive_root) / plan["source_sha256"][:16]
    marker_path = epoch / "archive_status.json"
    if not marker_path.exists():
        if old:
            raise ValueError("archived branch lacks marker for nonempty checkpoint")
        marker_indices = []
        status = "NO_ARCHIVE_MARKER_FOR_EPOCH"
    else:
        marker = json.loads(marker_path.read_text())
        marker_indices = marker.get("archived_shards")
        if (marker.get("source_sha256") != plan["source_sha256"]
                or marker.get("trade_gate") != "BLOCKED"
                or not isinstance(marker_indices, list)
                or any(type(i) is not int or not 0 <= i < plan["shard_count"]
                       for i in marker_indices)
                or len(marker_indices) != len(set(marker_indices))):
            raise ValueError("invalid archive marker or different source version")
        status = "NO_ORPHAN_SHARDS"
    orphan_indices = sorted(set(marker_indices) - old)
    if len(orphan_indices) > MAX_ORPHAN_REPLAY:
        raise ValueError("orphan archive recovery exceeds bounded four-shard limit")
    recovered = []
    for index in orphan_indices:
        path = epoch / f"shard_{index:04d}"
        # Re-validate receipt, member list, CSV bytes, OHLC and dates.
        report = verify(plan, [(index, path)], manifest_root)
        if (report["verified_shards"] != 1
                or report["verified_issuers"] != plan["shards"][index]["count"]
                or report["historical_PIT_verified"] is not False
                or report["trade_gate"] != "BLOCKED"):
            raise ValueError("orphan source replay did not pass")
        receipt = json.loads((path / "quality.json").read_text())
        recovered.append((index, receipt))
    updated = reconcile(plan, recovered, prior)
    validate_checkpoint(updated)
    if updated["completed_shards"] != len(old) + len(orphan_indices):
        raise ValueError("orphan recovery checkpoint count mismatch")
    if orphan_indices:
        status = "ORPHANS_REPLAYED_AWAITING_DURABLE_CHECKPOINT"
    result = {
        "phase": "P1_ORPHAN_ARCHIVE_RECOVERY",
        "source_sha256": plan["source_sha256"],
        "status": status,
        "checkpoint_shards_before": len(old),
        "recovered_archive_indices": orphan_indices,
        "recovered_shards": len(orphan_indices),
        "checkpoint_shards_after": updated["completed_shards"],
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    return updated, result


def main():
    ap = argparse.ArgumentParser()
    for name in ("plan", "root", "manifest-root", "out", "report"):
        ap.add_argument("--" + name, required=True)
    ap.add_argument("--prior")
    args = ap.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    prior = read(args.prior) if args.prior and Path(args.prior).exists() else None
    ledger, report = recover(
        read(args.plan), prior, args.root, args.manifest_root)
    for path, item in ((args.out, ledger), (args.report, report)):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
