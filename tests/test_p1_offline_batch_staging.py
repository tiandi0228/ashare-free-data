"""Offline staged-copy tests. No checkout writes, network, or trading."""
import tempfile
import unittest
from pathlib import Path

from collector.p1_offline_batch_staging import stage
from collector.p1_target_sha_readback import sha256
from tests.test_p1_bounded_missing_shard_batch_plan import BoundedBatchTests, COMMIT


class OfflineStagingTests(BoundedBatchTests):
    def setUp(self):
        super().setUp()
        self.out = self.source.parent / "scratch-output"

    def stage(self, proposal):
        return stage(proposal, self.handoff, self.source, self.target,
                     COMMIT, COMMIT, self.out)

    def test_staged_bytes_readback_and_private_target_unchanged(self):
        proposal = self.plan(max_shards=2)
        result = self.stage(proposal)
        self.assertEqual(result["status"], "SCRATCH_BYTES_SHA_MATCH_NOT_DESTINATION")
        self.assertEqual(result["staged_file_count"], 4)
        self.assertEqual(result["staged_bytes"], proposal["selected_bytes"])
        for row in proposal["selected_missing_files"]:
            self.assertEqual(sha256(self.out / "files" / row["path"]), row["sha256"])
        self.assertTrue((self.out / "stage_report.json").is_file())
        self.assertEqual(list(self.target.rglob("*")), [])
        self.assertFalse(result["migration_performed"])
        self.assertFalse(result["automatic_copy_authorized"])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_reject_existing_stage_and_no_repeated_overwrite(self):
        proposal = self.plan(max_shards=1)
        self.stage(proposal)
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.stage(proposal)

    def test_source_tamper_leaves_no_stage_or_target_change(self):
        proposal = self.plan()
        first = proposal["selected_missing_files"][0]["path"]
        (self.source / first).write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.stage(proposal)
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.target.rglob("*")), [])

    def test_changed_target_refuses_staging(self):
        proposal = self.plan()
        self.mirror(proposal["selected_missing_files"][0]["path"])
        with self.assertRaisesRegex(ValueError, "stale"):
            self.stage(proposal)
        self.assertFalse(self.out.exists())

    def test_stage_cannot_be_inside_source_or_target(self):
        proposal = self.plan()
        for bad in (self.source / "stage", self.target / "stage"):
            with self.subTest(output=str(bad)), self.assertRaisesRegex(
                ValueError, "overlaps"
            ):
                stage(proposal, self.handoff, self.source, self.target,
                      COMMIT, COMMIT, bad)


if __name__ == "__main__":
    unittest.main()
