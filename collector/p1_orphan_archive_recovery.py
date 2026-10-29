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
        "prior_completed_indices": sorted(old),
        "recovered_archive_indices": orphan_indices,
        "recovered_shards": len(orphan_indices),
        "checkpoint_shards_after": updated["completed_shards"],
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    return updated, result


def confirm_durable_recovery(proposed, remote, report):
    """Confirm that GitHub's *re-read* immutable epoch checkpoint contains
    every recovered receipt, not merely that the PUT command returned zero.
    """
    validate_checkpoint(proposed)
    validate_checkpoint(remote)
    if (not isinstance(report, dict)
            or report.get("phase") != "P1_ORPHAN_ARCHIVE_RECOVERY"
            or report.get("status") != "ORPHANS_REPLAYED_AWAITING_DURABLE_CHECKPOINT"
            or report.get("trade_gate") != "BLOCKED"
            or report.get("historical_PIT_verified") is not False
            or report.get("orders") != []
            or report.get("executable_candidates") != []):
        raise ValueError("invalid pending recovery acknowledgment")
    ids = report.get("recovered_archive_indices")
    if (not isinstance(ids, list) or not ids or len(ids) > MAX_ORPHAN_REPLAY
            or any(type(i) is not int for i in ids)
            or ids != sorted(set(ids))
            or report.get("recovered_shards") != len(ids)
            or report.get("checkpoint_shards_after") != proposed["completed_shards"]
            or report.get("source_sha256") != proposed["source_sha256"]
            or proposed["source_sha256"] != remote["source_sha256"]
            or proposed["shard_count"] != remote["shard_count"]):
        raise ValueError("recovery version or count mismatch")
    prior_indices = report.get("prior_completed_indices")
    if (not isinstance(prior_indices, list)
            or any(type(i) is not int for i in prior_indices)
            or prior_indices != sorted(set(prior_indices))
            or report.get("checkpoint_shards_before") != len(prior_indices)
            or set(prior_indices).intersection(ids)
            or set(prior_indices).union(ids) != {
                row["index"] for row in proposed["completed"]
            }):
        raise ValueError("recovery version or count mismatch")
    proposed_by_id = {row["index"]: row for row in proposed["completed"]}
    remote_by_id = {row["index"]: row for row in remote["completed"]}
    if not set(ids).issubset(proposed_by_id):
        raise ValueError("recovery report references unknown checkpoint shards")
    if any(remote_by_id.get(idx) != entry for idx, entry in proposed_by_id.items()):
        raise ValueError("remote checkpoint omitted or modified recovered evidence")
    return dict(
        report,
        status="ORPHANS_DURABLY_CHECKPOINTED",
        durable_recovered_indices=ids,
        durable_checkpoint_shards=remote["completed_shards"],
        checkpoint_readback_verified=True,
    )


def main():
    ap = argparse.ArgumentParser()
    for name in ("plan", "root", "manifest-root", "out", "report"):
        ap.add_argument("--" + name, required=True)
    ap.add_argument("--prior")
    ap.add_argument("--confirm-remote", help="Re-read epoch-specific remote checkpoint after write")
    args = ap.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    if args.confirm_remote:
        proposed = read(args.out)
        remote = read(args.confirm_remote)
        report = confirm_durable_recovery(proposed, remote, read(args.report))
        # A concurrent writer can legitimately add more same-epoch verified
        # shards after our proposed checkpoint was prepared. Never regress the
        # next picker to the older proposal after accepting that remote superset.
        Path(args.out).write_text(json.dumps(remote, ensure_ascii=False, indent=2) + "\n")
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False))
        return
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
