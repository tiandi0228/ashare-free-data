import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_target_sha_readback import reconcile

COMMIT = "a" * 40
EPOCH = "b" * 16


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.target = Path(temp.name) / "target"
        self.target.mkdir()
        self.files = {}
        for name, data in (
            (f"{EPOCH}/shard_0001/quality.json", b'{"trade_gate":"BLOCKED"}'),
            (f"{EPOCH}/shard_0001/sh_600001.csv", b"date,price\\n2026-11-09,3\\n"),
        ):
            self.files[name] = data
        rows = [{"path": name, "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in sorted(self.files.items())]
        sha = hashlib.sha256(json.dumps(
            rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()).hexdigest()
        self.handoff = {
            "phase": "P1_SOURCE_SHA_HANDOFF_NO_DESTINATION_ATTESTATION",
            "status": "SOURCE_MANIFEST_REPLAYED_TARGET_UNVERIFIED",
            "canonical_inventory_format": "JSON_SORT_KEYS_COMPACT_UTF8_SORTED_BY_PATH",
            "source_manifest_has_no_archive_status_files": True,
            "original_paths_and_sha256": rows,
            "eligible_original_files": 2,
            "source_file_inventory_sha256": sha,
            "destination_files_verified": False,
            "migration_performed": False,
            "automatic_copy_authorized": False,
            "writer_cutover_authorized": False,
            "historical_PIT_verified": False,
            "trade_gate": "BLOCKED",
            "orders": [], "executable_candidates": [],
        }

    def write(self, name, data):
        p = self.target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def test_partial_target_and_separate_status_do_not_certify(self):
        self.write(next(iter(self.files)), next(iter(self.files.values())))
        self.write(f"{EPOCH}/archive_status.json", b'{"trade_gate":"BLOCKED"}')
        report = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(report["status"], "TARGET_PARTIAL_SOURCE_HANDOFF_READBACK")
        self.assertEqual(report["matching_file_count"], 1)
        self.assertEqual(report["missing_file_count"], 1)
        self.assertEqual(report["separate_unverified_status_file_count"], 1)
        self.assertFalse(report["destination_mirror_verified"])
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertEqual(report["orders"], [])

    def test_matching_bytes_still_not_migration_certification(self):
        for name, raw in self.files.items():
            self.write(name, raw)
        report = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(report["status"], "TARGET_BYTES_MATCH_SOURCE_HANDOFF_NOT_CERTIFIED")
        self.assertEqual(report["matching_file_count"], 2)
        self.assertEqual(report["missing_file_count"], 0)
        self.assertFalse(report["destination_files_verified"])
        self.assertFalse(report["writer_cutover_authorized"])

    def test_tampered_and_unallowlisted_bytes_are_reported(self):
        for name, raw in self.files.items():
            self.write(name, raw)
        self.write(f"{EPOCH}/shard_0001/sh_600001.csv", b"tampered")
        self.write(f"{EPOCH}/shard_0024/sh_600024.csv", b"quarantine")
        report = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(report["status"], "TARGET_CONFLICT_OR_UNALLOWLISTED")
        self.assertEqual(report["conflicting_file_count"], 1)
        self.assertEqual(report["unallowlisted_target_file_count"], 1)
        self.assertFalse(report["automatic_copy_authorized"])

    def test_unknown_target_file_fails_closed(self):
        self.write("p4-current-tail/report.json", b"unknown")
        report = reconcile(self.handoff, self.target, COMMIT)
        self.assertEqual(report["unallowlisted_target_file_count"], 1)
        self.assertEqual(report["status"], "TARGET_CONFLICT_OR_UNALLOWLISTED")

    def test_manifest_tamper_and_duplicate_rejected(self):
        changed = copy.deepcopy(self.handoff)
        changed["original_paths_and_sha256"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            reconcile(changed, self.target, COMMIT)
        changed = copy.deepcopy(self.handoff)
        changed["original_paths_and_sha256"].append(
            copy.deepcopy(changed["original_paths_and_sha256"][0]))
        changed["eligible_original_files"] = 3
        with self.assertRaises(ValueError):
            reconcile(changed, self.target, COMMIT)

    def test_symlink_rejected_and_no_data_modified(self):
        target = self.target / f"{EPOCH}/shard_0001/quality.json"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            reconcile(self.handoff, self.target, COMMIT)
        self.assertTrue(target.is_symlink())

    def test_readback_requires_frozen_commit_and_blocked_handoff(self):
        with self.assertRaisesRegex(ValueError, "immutable Git SHA"):
            reconcile(self.handoff, self.target, "main")
        changed = copy.deepcopy(self.handoff)
        changed["trade_gate"] = "OPEN"
        with self.assertRaisesRegex(ValueError, "untrusted"):
            reconcile(changed, self.target, COMMIT)


if __name__ == "__main__":
    unittest.main()
