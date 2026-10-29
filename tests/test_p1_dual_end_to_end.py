"""Offline end-to-end contract for bounded dual research shards (NO TRADES).

Exercises real parsers, second-shard acceptance, immutable checkpoint
reconciliation, archive collections and deep replay without network access.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from collector.baostock_batch import FIELDS
from collector.p1_archive_audit import audit
from collector.p1_checkpoint import validate as validate_checkpoint
from collector.p1_csv_archive import collect
from collector.p1_optional_second import accept_verified_second, decide
from collector.p1_quad_verify import verify
from collector.p1_run_progress import assess
from collector.p1_shard_ledger import reconcile


class DualShardEndToEndTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source_sha = "a" * 64
        self.codes = ("sh.600000", "sz.000001")
        self.shards = []
        self.receipts = []
        self.manifest_root = self.root / "shards"
        self.manifest_root.mkdir()
        for index, code in enumerate(self.codes):
            manifest = (code + "\n").encode()
            name = f"shard_{index:04d}.txt"
            (self.manifest_root / name).write_bytes(manifest)
            self.shards.append({
                "index": index, "name": name, "count": 1,
                "sha256": hashlib.sha256(manifest).hexdigest()})
            folder = self.root / f"source_{index}"
            folder.mkdir()
            row = ["2026-10-20", code, "6.40", "6.50", "6.30",
                   "6.40", "1000", "6400", "3", "1"]
            raw = (",".join(FIELDS) + "\n" + ",".join(row) + "\n").encode()
            (folder / (code.replace(".", "_") + ".csv")).write_bytes(raw)
            receipt = {
                "status": "OBSERVED_SUBSET_UNVERIFIED",
                "manifest_sha256": self.shards[index]["sha256"],
                "issuer_count": 1, "query_attempts": 1,
                "paid_api_calls": 0, "trade_gate": "BLOCKED",
                "orders": [], "executable_candidates": [],
                "results": [{
                    "code": code, "status": "OBSERVED_UNVERIFIED",
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "rows": 1, "first": "2026-10-20", "last": "2026-10-20",
                    "tradable_rows": 1, "suspended_status_rows": 0,
                }],
            }
            (folder / "quality.json").write_text(json.dumps(receipt))
            self.receipts.append((index, folder, receipt))
        self.plan = {
            "phase": "P1_FRESH_VENDOR_SHARD_PLAN",
            "source_sha256": self.source_sha, "shard_count": 2,
            "shards": self.shards, "trade_gate": "BLOCKED",
            "historical_PIT_verified": False, "issuer_count": 2,
        }
        self.plan_path = self.root / "plan.json"
        self.plan_path.write_text(json.dumps(self.plan))
        self.empty_ledger = reconcile(self.plan, [])
        validate_checkpoint(self.empty_ledger)

    def archive_and_report(self, included, policy):
        chosen = [(idx, folder) for idx, folder, _ in self.receipts
                  if idx in included]
        replay = verify(self.plan, chosen, self.manifest_root)
        self.assertEqual(replay["verified_shards"], len(included))
        self.assertFalse(replay["historical_PIT_verified"])
        self.assertEqual(len(collect(self.plan, chosen)), len(included))
        new_ledger = reconcile(
            self.plan,
            [(idx, receipt) for idx, _, receipt in self.receipts
             if idx in included],
            self.empty_ledger)
        validate_checkpoint(new_ledger)
        archive_root = self.root / "archive"
        epoch = archive_root / self.source_sha[:16]
        epoch.mkdir(parents=True)
        (epoch / "archive_status.json").write_text(json.dumps({
            "source_sha256": self.source_sha,
            "trade_gate": "BLOCKED", "archived_shards": sorted(included)}))
        for idx, folder in chosen:
            dest = epoch / f"shard_{idx:04d}"
            shutil.copytree(folder, dest)
        archived = audit(self.plan, new_ledger, archive_root, replay=True)
        self.assertTrue(archived["archive_csv_replay_enabled"])
        self.assertEqual(archived["archive_gap_issuers"], 0)
        selected = {
            "selected_shards": [0, 1], "selected_count": 2,
            "trade_gate": "BLOCKED",
        }
        progress = assess(self.plan, new_ledger, archived,
                          selected, policy, self.empty_ledger)
        self.assertEqual(progress["status"], "DURABLE_PROGRESS")
        self.assertEqual(progress["new_shards_durably_accepted"],
                         len(included))
        self.assertEqual(progress["archive_gap_issuers"], 0)
        self.assertEqual(progress["trade_gate"], "BLOCKED")
        self.assertEqual(progress["orders"], [])
        self.assertEqual(progress["executable_candidates"], [])
        return new_ledger, progress

    def test_both_valid_shards_reach_deep_archive_and_checkpoint(self):
        policy = accept_verified_second(
            decide("true", "success", "0001"),
            self.plan_path, self.manifest_root, self.receipts[1][1])
        self.assertEqual(policy["status"], "SECOND_SHARD_VERIFIED")
        self.assertTrue(policy["accepted_second"])
        ledger, report = self.archive_and_report([0, 1], policy)
        self.assertEqual(ledger["completed_shards"], 2)
        self.assertEqual(ledger["completed_issuers"], 2)
        self.assertEqual(report["effective_shard_count"], 2)
        self.assertEqual(report["dual_pilot_result"], "TWO_VERIFIED_SHARDS_ARCHIVED")

    def test_tampered_second_csv_preserves_first_deep_archival(self):
        second = self.receipts[1][1]
        (second / "sz_000001.csv").write_bytes(b"tampered")
        policy = accept_verified_second(
            decide("true", "success", "0001"),
            self.plan_path, self.manifest_root, second)
        self.assertEqual(policy["status"], "SECOND_INVALID_PRESERVE_FIRST")
        self.assertFalse(policy["accepted_second"])
        self.assertEqual(policy["effective_shard_count"], 1)
        ledger, report = self.archive_and_report([0], policy)
        self.assertEqual(ledger["completed_shards"], 1)
        self.assertEqual(ledger["pending_shards"], [1])
        self.assertEqual(report["new_selected_shards"], [0])
        self.assertEqual(report["dual_pilot_result"], "FIRST_ARCHIVED_SECOND_REJECTED")

    def test_failed_second_fetch_does_not_drop_first_verified_receipt(self):
        policy = accept_verified_second(
            decide("true", "failure", "0001"),
            self.plan_path, self.manifest_root, self.receipts[1][1])
        self.assertEqual(policy["status"], "SECOND_FAILED_PRESERVE_FIRST")
        ledger, report = self.archive_and_report([0], policy)
        self.assertEqual(ledger["completed_shards"], 1)
        self.assertEqual(report["new_shards_durably_accepted"], 1)
        self.assertEqual(report["dual_pilot_result"], "FIRST_ARCHIVED_SECOND_REJECTED")


if __name__ == "__main__":
    unittest.main()
