"""Reconcile P1 and P2 at two immutable snapshots, without writing either ledger."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from collector.p1_active_migration_checkpoint import resolve
from collector.p2_original_gap_window_triage import check_current_checkpoint


def audit_snapshot(root):
    read = lambda path: json.loads(path.read_bytes())
    lock = resolve(root / "checkpoint")
    epoch = lock["source_sha256"][:16]
    checkpoint = read(root / "checkpoint" / lock["checkpoint_path"])
    archive = root / "archive" / epoch
    status = read(archive / "archive_status.json")
    coverage = read(root / "coverage" / "summaries" / f"{epoch}.json")
    witness = check_current_checkpoint(coverage, checkpoint, status)
    ids = {f"shard_{i:04d}" for i in status["archived_shards"]}
    if ids != {p.name for p in archive.glob("shard_*") if p.is_dir()}:
        raise ValueError("archive status differs from persisted shard directories")
    return witness, ids, coverage, checkpoint, status, archive


@unittest.skipUnless(os.environ.get("P2_DELTA_ROOT"), "requires pinned archive snapshots")
class ArchivedCoverageDelta(unittest.TestCase):
    def test_scheduled_and_manual_shards_are_counted_once(self):
        root = Path(os.environ["P2_DELTA_ROOT"])
        prior, old_ids, old_coverage, _, _, _ = audit_snapshot(root / "prior")
        current, new_ids, coverage, checkpoint, status, archive = audit_snapshot(root / "current")
        self.assertEqual(prior["source_epoch_sha256"], current["source_epoch_sha256"])
        self.assertEqual((prior["checkpoint_completed_shards"], current["checkpoint_completed_shards"]),
                         (325, 332))
        with self.assertRaisesRegex(ValueError, "stale or unsafe"):
            check_current_checkpoint(old_coverage, checkpoint, status)
        self.assertLess(old_ids, new_ids)
        added = new_ids - old_ids
        self.assertEqual(added, {f"shard_{i:04d}" for i in [247, 248, 317, 318, 319, 320, 321]})
        self.assertFalse(added.intersection(coverage["gap_shard_ids"]))
        self.assertEqual(old_coverage["gap_issuer_codes"], coverage["gap_issuer_codes"])
        self.assertEqual(coverage["issuer_evidence_gap_count"], 23)
        self.assertEqual(coverage["feature_complete_shards"], 310)
        self.assertEqual(coverage["feature_issuer_count"] - old_coverage["feature_issuer_count"], 56)
        self.assertEqual(coverage["feature_issuer_count"], 2627)
        self.assertEqual(checkpoint["pending_shards"][:2], [249, 250])
        self.assertEqual(len(checkpoint["pending_shards"]), 68)

        verified = set()
        checkpoint_rows = {r["index"]: r for r in checkpoint["completed"]}
        for shard in sorted(added):
            folder = archive / shard
            quality = (folder / "quality.json").read_bytes()
            receipt = json.loads(quality)
            entry = checkpoint_rows[int(shard.removeprefix("shard_"))]
            self.assertEqual(receipt["manifest_sha256"], entry["manifest_sha256"])
            self.assertEqual(len(receipt["results"]), 8)
            for row in receipt["results"]:
                issuer = row["code"]
                self.assertNotIn(issuer, verified)
                verified.add(issuer)
                raw = (folder / (issuer.replace(".", "_") + ".csv")).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"], issuer)
        self.assertEqual(len(verified), 56)
        self.assertEqual(current["trade_gate"], "BLOCKED")
        self.assertIs(current["historical_PIT_verified"], False)
