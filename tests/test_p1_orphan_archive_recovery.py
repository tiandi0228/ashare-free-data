import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.baostock_batch import FIELDS
from collector.p1_orphan_archive_recovery import recover, confirm_durable_recovery
from collector.p1_shard_ledger import reconcile


class OrphanArchiveRecoveryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.manifests = self.root / "manifests"
        self.manifests.mkdir()
        self.archive = self.root / "research_archive"
        self.epoch = self.archive / ("a" * 16)
        self.epoch.mkdir(parents=True)
        self.plan = {
            "phase": "P1_FRESH_VENDOR_SHARD_PLAN",
            "source_sha256": "a" * 64,
            "shard_count": 2,
            "trade_gate": "BLOCKED",
            "historical_PIT_verified": False,
            "shards": [],
        }
        self.receipts = {}
        for i, code in enumerate(("sh.600000", "sz.000001")):
            raw_manifest = (code + "\n").encode()
            name = f"shard_{i:04d}.txt"
            (self.manifests / name).write_bytes(raw_manifest)
            manifest_sha = hashlib.sha256(raw_manifest).hexdigest()
            self.plan["shards"].append({
                "index": i, "count": 1, "sha256": manifest_sha, "name": name,
            })
            part = self.epoch / f"shard_{i:04d}"
            part.mkdir()
            record = ["2026-10-20", code, "6.40", "6.50",
                      "6.30", "6.40", "1000", "6400", "3", "1"]
            raw_csv = (",".join(FIELDS) + "\n" + ",".join(record) + "\n").encode()
            (part / (code.replace(".", "_") + ".csv")).write_bytes(raw_csv)
            receipt = {
                "status": "OBSERVED_SUBSET_UNVERIFIED",
                "trade_gate": "BLOCKED",
                "paid_api_calls": 0,
                "manifest_sha256": manifest_sha,
                "query_attempts": 1, "issuer_count": 1,
                "results": [{
                    "code": code, "status": "OBSERVED_UNVERIFIED",
                    "rows": 1, "first": "2026-10-20", "last": "2026-10-20",
                    "tradable_rows": 1, "suspended_status_rows": 0,
                    "sha256": hashlib.sha256(raw_csv).hexdigest(),
                }],
            }
            (part / "quality.json").write_text(json.dumps(receipt))
            self.receipts[i] = receipt
        self.prior = reconcile(self.plan, [(0, self.receipts[0])])

    def marker(self, indices, **changes):
        item = {
            "source_sha256": self.plan["source_sha256"],
            "trade_gate": "BLOCKED",
            "archived_shards": indices,
        }
        item.update(changes)
        (self.epoch / "archive_status.json").write_text(json.dumps(item))

    def test_archive_only_second_replayed_into_existing_checkpoint(self):
        self.marker([0, 1])
        recovered, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        self.assertEqual(recovered["completed_shards"], 2)
        self.assertEqual(recovered["completed_issuers"], 2)
        self.assertEqual(recovered["pending_shards"], [])
        self.assertEqual(report["recovered_archive_indices"], [1])
        self.assertEqual(report["checkpoint_shards_before"], 1)
        self.assertEqual(report["checkpoint_shards_after"], 2)
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertEqual(report["orders"], [])
        self.assertFalse(report["historical_PIT_verified"])
        original = self.prior["completed"][0]
        self.assertEqual(recovered["completed"][0], original)

    def test_no_orphan_does_not_modify_existing_checkpoint(self):
        self.marker([0])
        result, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        self.assertEqual(result["completed"], self.prior["completed"])
        self.assertEqual(report["status"], "NO_ORPHAN_SHARDS")
        self.assertEqual(report["recovered_shards"], 0)

    def test_no_marker_for_new_epoch_is_not_a_fabricated_recovery(self):
        result, report = recover(
            self.plan, None, self.archive, self.manifests)
        self.assertEqual(result["completed_shards"], 0)
        self.assertEqual(report["status"], "NO_ARCHIVE_MARKER_FOR_EPOCH")

    def test_missing_archive_marker_for_nonempty_checkpoint_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"lacks marker"):
            recover(self.plan, self.prior, self.archive, self.manifests)

    def test_workflow_recovers_orphans_before_selecting_new_shards(self):
        workflow=(Path(__file__).resolve().parents[1]/
                  ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        recovery=workflow.index(
            "      - name: Recover previously archived but uncheckpointed research shards")
        selection=workflow.index(
            "      - name: Select up to four distinct missing frozen roster shards")
        self.assertLess(recovery,selection)
        block=workflow[recovery:selection]
        self.assertIn("python -m collector.p1_orphan_archive_recovery",block)
        self.assertIn("RECOVERED=",block)
        self.assertIn("if [[ \"$RECOVERED\" -gt 0 ]]",block)
        self.assertIn("python -m collector.p1_checkpoint --mode write",block)
        self.assertIn("cp evidence/recovered_ledger.json evidence/prior_ledger.json",block)
        self.assertIn("evidence/orphan_recovery.json",workflow)
        self.assertIn("tests.test_p1_orphan_archive_recovery",workflow)

    def test_malformed_archive_marker_is_rejected(self):
        for indices in ([0, 1, 1], [-1], [True], [2], [{"index": 1}]):
            with self.subTest(indices=indices):
                self.marker(indices)
                with self.assertRaises(ValueError):
                    recover(self.plan, self.prior, self.archive, self.manifests)
        self.marker([0, 1], source_sha256="b" * 64)
        with self.assertRaisesRegex(ValueError, "archive marker"):
            recover(self.plan, self.prior, self.archive, self.manifests)

    def test_tampered_orphan_csv_cannot_be_added_to_checkpoint(self):
        self.marker([0, 1])
        (self.epoch / "shard_0001" / "sz_000001.csv").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            recover(self.plan, self.prior, self.archive, self.manifests)
        self.assertEqual(self.prior["completed_shards"], 1)

    def test_cross_epoch_checkpoint_rejected(self):
        self.marker([0, 1])
        old = dict(self.prior, source_sha256="b" * 64)
        with self.assertRaisesRegex(ValueError, "cross-epoch"):
            recover(self.plan, old, self.archive, self.manifests)

    def test_multiple_orphans_recovered_from_absent_checkpoint(self):
        self.marker([0, 1])
        ledger, report = recover(self.plan, None, self.archive, self.manifests)
        self.assertEqual(ledger["completed_shards"], 2)
        self.assertEqual(report["recovered_archive_indices"], [0, 1])

    def test_remote_readback_confirms_all_orphan_receipts(self):
        self.marker([0, 1])
        proposed, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        confirmed = confirm_durable_recovery(proposed, proposed, report)
        self.assertEqual(confirmed["status"],"ORPHANS_DURABLY_CHECKPOINTED")
        self.assertTrue(confirmed["checkpoint_readback_verified"])
        self.assertEqual(confirmed["durable_recovered_indices"],[1])
        self.assertEqual(confirmed["durable_checkpoint_shards"],2)
        self.assertEqual(confirmed["trade_gate"],"BLOCKED")
        self.assertEqual(confirmed["orders"],[])

    def test_remote_without_recovered_orphan_cannot_acknowledge(self):
        self.marker([0,1])
        proposed, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        with self.assertRaisesRegex(ValueError,"omitted or modified"):
            confirm_durable_recovery(proposed, self.prior, report)

    def test_remote_replaced_receipt_cannot_acknowledge(self):
        self.marker([0,1])
        proposed, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        remote = dict(proposed)
        remote["completed"] = [dict(item) for item in proposed["completed"]]
        remote["completed"][1]["receipt_sha256"] = "e"*64
        with self.assertRaisesRegex(ValueError,"omitted or modified"):
            confirm_durable_recovery(proposed, remote, report)

    def test_wrong_remote_epoch_or_unsafe_acknowledgment_is_blocked(self):
        self.marker([0,1])
        proposed, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        wrong = dict(proposed, source_sha256="b"*64)
        with self.assertRaisesRegex(ValueError,"version or count mismatch"):
            confirm_durable_recovery(proposed, wrong, report)
        untrusted = dict(report, trade_gate="OPEN")
        with self.assertRaisesRegex(ValueError,"pending recovery acknowledgment"):
            confirm_durable_recovery(proposed, proposed, untrusted)

    def test_acknowledgment_does_not_accept_unrelated_orphan_ids(self):
        self.marker([0,1])
        proposed, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        forged = dict(report, recovered_archive_indices=[0])
        with self.assertRaisesRegex(ValueError,"unknown checkpoint shards|version or count mismatch"):
            confirm_durable_recovery(proposed, self.prior, forged)

    def test_workflow_rechecks_remote_before_reusing_recovered_ledger(self):
        workflow=(Path(__file__).resolve().parents[1]/
                  ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        start=workflow.index(
            "      - name: Recover previously archived but uncheckpointed research shards")
        end=workflow.index("      - name: Select up to four distinct missing frozen roster shards",start)
        block=workflow[start:end]
        self.assertIn("remote_read(os.environ['GITHUB_REPOSITORY']",block)
        self.assertIn("epoch_path(proposed['source_sha256'])",block)
        self.assertIn("--confirm-remote evidence/recovery_remote_ack.json",block)
        self.assertLess(block.index("--confirm-remote"),block.index(
            "cp evidence/recovered_ledger.json evidence/prior_ledger.json"))

    def test_cli_acknowledgment_persists_only_after_remote_readback(self):
        from unittest.mock import patch
        from collector.p1_orphan_archive_recovery import main
        self.marker([0,1])
        proposed, report = recover(
            self.plan, self.prior, self.archive, self.manifests)
        planned = self.root / "plan.json"
        proposed_path = self.root / "proposed.json"
        remote_path = self.root / "remote.json"
        receipt_path = self.root / "recovery.json"
        planned.write_text(json.dumps(self.plan))
        proposed_path.write_text(json.dumps(proposed))
        remote_path.write_text(json.dumps(proposed))
        receipt_path.write_text(json.dumps(report))
        args=["p1_orphan_archive_recovery",
              "--plan",str(planned),
              "--root",str(self.archive),
              "--manifest-root",str(self.manifests),
              "--out",str(proposed_path),
              "--report",str(receipt_path),
              "--confirm-remote",str(remote_path)]
        with patch("sys.argv",args):
            main()
        confirmed=json.loads(receipt_path.read_text())
        self.assertEqual(confirmed["status"],"ORPHANS_DURABLY_CHECKPOINTED")
        self.assertTrue(confirmed["checkpoint_readback_verified"])
        self.assertEqual(confirmed["durable_recovered_indices"],[1])

    def test_non_mainboard_manifest_cannot_be_recovered(self):
        self.marker([0, 1])
        self.plan["shards"][1]["count"] = 2
        with self.assertRaises(ValueError):
            recover(self.plan, self.prior, self.archive, self.manifests)


if __name__ == "__main__":
    unittest.main()
