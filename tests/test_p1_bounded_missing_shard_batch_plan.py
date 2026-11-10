import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_bounded_missing_shard_batch_plan import build

EPOCH = "a" * 16
COMMIT = "b" * 40


class BoundedBatchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.source = root / "source"
        self.target = root / "target"
        self.source.mkdir()
        self.target.mkdir()
        rows = []
        for n in (0, 1, 2):
            for name, data in (
                ("quality.json", b'{"trade_gate":"BLOCKED"}'),
                (f"sh_{600000+n}.csv", f"date,price\n2026-11-09,{n}\n".encode()),
            ):
                relative = f"{EPOCH}/shard_{n:04d}/{name}"
                path = self.source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                rows.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest()})
        rows.sort(key=lambda x: x["path"])
        manifest = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.handoff = {
            "phase": "P1_SOURCE_SHA_HANDOFF_NO_DESTINATION_ATTESTATION",
            "status": "SOURCE_MANIFEST_REPLAYED_TARGET_UNVERIFIED",
            "canonical_inventory_format": "JSON_SORT_KEYS_COMPACT_UTF8_SORTED_BY_PATH",
            "source_manifest_has_no_archive_status_files": True,
            "original_paths_and_sha256": rows,
            "eligible_original_files": len(rows),
            "source_file_inventory_sha256": hashlib.sha256(manifest).hexdigest(),
            "destination_files_verified": False,
            "migration_performed": False,
            "automatic_copy_authorized": False,
            "writer_cutover_authorized": False,
            "historical_PIT_verified": False,
            "trade_gate": "BLOCKED",
            "orders": [],
            "executable_candidates": [],
        }

    def plan(self, **kwargs):
        return build(self.handoff, self.source, self.target, COMMIT, COMMIT, **kwargs)

    def mirror(self, name):
        path = self.target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((self.source / name).read_bytes())

    def test_ordered_bounded_full_shards_and_digest(self):
        result = self.plan(max_shards=2)
        self.assertEqual(result["status"], "REVIEWABLE_MISSING_SHARD_BATCH_NO_WRITE")
        self.assertEqual(result["selected_shards"], [
            f"{EPOCH}/shard_0000", f"{EPOCH}/shard_0001"])
        self.assertEqual(result["selected_file_count"], 4)
        self.assertEqual(result["unselected_missing_files"], 2)
        self.assertFalse(result["automatic_copy_authorized"])
        self.assertFalse(result["migration_performed"])
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["selected_inventory_sha256"],
                         self.plan(max_shards=2)["selected_inventory_sha256"])

    def test_existing_matching_file_not_retransferred(self):
        first = self.handoff["original_paths_and_sha256"][0]["path"]
        self.mirror(first)
        result = self.plan(max_shards=1)
        self.assertEqual(result["target_matching_file_count"], 1)
        self.assertEqual(result["selected_file_count"], 1)
        self.assertEqual(result["selected_shards"], [f"{EPOCH}/shard_0000"])
        self.assertNotIn(first, [x["path"] for x in result["selected_missing_files"]])

    def test_target_conflict_or_unallowlisted_blocks_all_batches(self):
        first = self.handoff["original_paths_and_sha256"][0]["path"]
        path = self.target / first
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "target has conflicting"):
            self.plan()
        path.unlink()
        bad = self.target / f"{EPOCH}/shard_0024/sh_600024.csv"
        bad.parent.mkdir(parents=True)
        bad.write_bytes(b"quarantined")
        with self.assertRaisesRegex(ValueError, "unallowlisted"):
            self.plan()

    def test_source_tamper_or_symlink_blocks_batch(self):
        first = self.handoff["original_paths_and_sha256"][0]["path"]
        src = self.source / first
        src.write_bytes(b"tamper")
        with self.assertRaisesRegex(ValueError, "source original SHA mismatch"):
            self.plan()
        src.unlink()
        src.symlink_to(self.target)
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.plan()

    def test_small_budget_fails_closed_without_skipping_first_shard(self):
        report = self.plan(max_bytes=1)
        self.assertEqual(report["status"], "FIRST_MISSING_SHARD_EXCEEDS_BUDGET_NO_WRITE")
        self.assertEqual(report["selected_file_count"], 0)
        self.assertEqual(report["unselected_missing_files"], 6)
        with self.assertRaises(ValueError):
            self.plan(max_shards=5)
        with self.assertRaises(ValueError):
            self.plan(max_bytes=25 * 1024 * 1024 + 1)

    def test_all_allowlisted_files_present_no_write(self):
        for row in self.handoff["original_paths_and_sha256"]:
            self.mirror(row["path"])
        report = self.plan()
        self.assertEqual(report["status"], "NO_MISSING_ALLOWLIST_FILES")
        self.assertEqual(report["selected_missing_files"], [])
        self.assertFalse(report["destination_mirror_verified"])
        self.assertFalse(report["writer_cutover_authorized"])

    def test_forged_handoff_and_commit_rejected(self):
        changed = copy.deepcopy(self.handoff)
        changed["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError):
            build(changed, self.source, self.target, COMMIT, COMMIT)
        with self.assertRaises(ValueError):
            build(self.handoff, self.source, self.target, "main", COMMIT)

    def test_shard_group_missing_receipt_fails_closed(self):
        changed = copy.deepcopy(self.handoff)
        rows = [p for p in changed["original_paths_and_sha256"]
                if not p["path"].endswith("shard_0000/quality.json")]
        changed["original_paths_and_sha256"] = rows
        changed["eligible_original_files"] = len(rows)
        canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        changed["source_file_inventory_sha256"] = hashlib.sha256(canonical).hexdigest()
        with self.assertRaisesRegex(ValueError, "incomplete handoff shard"):
            build(changed, self.source, self.target, COMMIT, COMMIT)


if __name__ == "__main__":
    unittest.main()
