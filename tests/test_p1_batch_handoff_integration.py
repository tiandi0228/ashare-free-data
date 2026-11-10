"""Integration of P1 original receipts, independent replay, private-target readback
and bounded review-only selection. No private repo or live migration involved.
"""
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_partial_sha_copy_plan import plan
from collector.p1_source_sha_handoff import build as make_handoff
from collector.p1_source_handoff_independent_replay import replay
from collector.p1_target_sha_readback import reconcile
from collector.p1_bounded_missing_shard_batch_plan import build as next_batch
from tests.test_p1_partial_sha_copy_plan import build_epoch
from tests.test_p1_source_sha_handoff import ACTIVE, OLD, readiness, gaps

COMMIT = "c" * 40


class P1FullReadOnlyChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "source"
        self.target = root / "private-target"
        self.source.mkdir()
        self.target.mkdir()
        build_epoch(self.source, ACTIVE)
        build_epoch(self.source, OLD, missing=(1,))
        partial = plan(self.source, ACTIVE)
        self.handoff = make_handoff(partial, readiness(), gaps())
        self.independent = replay(self.source, self.handoff)

    def copy_sample_to_staging(self, rel):
        src = self.source / rel
        dst = self.target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    def test_initial_plan_is_pinned_ordered_and_non_writable(self):
        self.assertEqual(self.independent["source_files_replayed"], 6)
        self.assertEqual(
            self.independent["source_file_inventory_sha256"],
            self.handoff["source_file_inventory_sha256"],
        )
        initial = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(initial["missing_file_count"], 6)
        batch = next_batch(self.handoff, self.source, self.target, COMMIT, COMMIT,
                           max_shards=2)
        self.assertEqual(len(batch["selected_shards"]), 2)
        self.assertEqual(batch["selected_file_count"], 4)
        self.assertEqual(batch["unselected_missing_files"], 2)
        self.assertEqual(batch["target_missing_file_count"], initial["missing_file_count"])
        self.assertEqual(batch["source_file_inventory_sha256"],
                         self.independent["source_file_inventory_sha256"])
        for key in ("migration_performed", "automatic_copy_authorized",
                    "writer_cutover_authorized", "destination_mirror_verified"):
            self.assertIs(batch[key], False, key)
        self.assertEqual(batch["trade_gate"], "BLOCKED")
        self.assertEqual(batch["orders"], [])
        self.assertFalse(any(OLD[:16] + "/shard_0001" in row["path"]
                             for row in batch["selected_missing_files"]))

    def test_staging_one_batch_replans_without_duplicate_paths(self):
        first = next_batch(self.handoff, self.source, self.target, COMMIT, COMMIT,
                           max_shards=2)
        for row in first["selected_missing_files"]:
            self.copy_sample_to_staging(row["path"])
        after = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(after["matching_file_count"], 4)
        self.assertEqual(after["missing_file_count"], 2)
        second = next_batch(self.handoff, self.source, self.target, COMMIT, COMMIT,
                            max_shards=2)
        self.assertEqual(second["selected_file_count"], 2)
        self.assertFalse(set(x["path"] for x in first["selected_missing_files"]) &
                         set(x["path"] for x in second["selected_missing_files"]))
        self.assertFalse(second["migration_performed"])
        for row in second["selected_missing_files"]:
            self.copy_sample_to_staging(row["path"])
        final = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(final["missing_file_count"], 0)
        self.assertEqual(final["matching_file_count"], 6)
        self.assertIs(final["destination_mirror_verified"], False)
        self.assertIs(final["writer_cutover_authorized"], False)
        self.assertEqual(
            next_batch(self.handoff, self.source, self.target, COMMIT, COMMIT)["status"],
            "NO_MISSING_ALLOWLIST_FILES",
        )

    def test_tampered_target_blocks_a_new_batch(self):
        first = next_batch(self.handoff, self.source, self.target, COMMIT, COMMIT)
        rel = first["selected_missing_files"][0]["path"]
        self.copy_sample_to_staging(rel)
        (self.target / rel).write_bytes(b"modified after staging")
        with self.assertRaisesRegex(ValueError, "conflicting"):
            next_batch(self.handoff, self.source, self.target, COMMIT, COMMIT)


if __name__ == "__main__":
    unittest.main()
