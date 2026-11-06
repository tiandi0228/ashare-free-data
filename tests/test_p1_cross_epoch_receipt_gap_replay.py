import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_cross_epoch_receipt_gap_replay import audit

OLD = "a" * 64
NEW = "b" * 64


class CrossEpochGapTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.old = self.root / OLD[:16]
        self.new = self.root / NEW[:16]
        self.old.mkdir()
        self.new.mkdir()
        for ep, sha in ((self.old, OLD), (self.new, NEW)):
            (ep / "archive_status.json").write_text(json.dumps({
                "source_sha256": sha, "trade_gate": "BLOCKED", "archived_shards": [24, 25]
            }))
        for index in (24, 25):
            old = self.old / f"shard_{index:04d}"
            new = self.new / f"shard_{index:04d}"
            old.mkdir()
            new.mkdir()
            raw = f"date,close\n2026-01-{index},2.5\n".encode()
            (old / "sh_600258.csv").write_bytes(raw)
            (new / "sh_600258.csv").write_bytes(raw)
            (new / "quality.json").write_text(json.dumps({
                "status": "OBSERVED_SUBSET_UNVERIFIED", "trade_gate": "BLOCKED",
                "results": [{"code": "sh.600258", "sha256": hashlib.sha256(raw).hexdigest()}]
            }))

    def test_match_does_not_restore_original_receipt(self):
        report = audit(self.root, OLD, NEW)
        self.assertEqual(report["matching_files"], 2)
        self.assertEqual(report["different_files"], 0)
        self.assertEqual(report["missing_original_receipts_recovered"], 0)
        self.assertFalse(report["legacy_receipts_authenticated"])
        self.assertFalse(report["writer_cutover_authorized"])
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertEqual(report["orders"], [])
        self.assertFalse((self.old / "shard_0024" / "quality.json").exists())

    def test_different_comparison_bytes_are_not_accepted(self):
        (self.new / "shard_0024" / "sh_600258.csv").write_bytes(b"changed")
        report = audit(self.root, OLD, NEW)
        self.assertEqual(report["different_files"], 1)
        self.assertEqual(report["matching_files"], 1)
        self.assertEqual(report["shards"][0]["files"][0]["result"], "COMPARISON_RECEIPT_SHA_MISMATCH")

    def test_no_comparison_receipt_not_a_success(self):
        (self.new / "shard_0025" / "quality.json").unlink()
        report = audit(self.root, OLD, NEW)
        self.assertEqual(report["matching_files"], 1)
        self.assertEqual(report["missing_comparison_files"], 1)
        self.assertFalse(report["source_archive_sha_verified"])

    def test_legacy_original_receipt_present_rejects_gap_scenario(self):
        (self.old / "shard_0025" / "quality.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "not a missing-receipt case"):
            audit(self.root, OLD, NEW)

    def test_unsafe_legacy_csv_symlink_rejected(self):
        f = self.old / "shard_0024" / "sh_600258.csv"
        target = self.root / "outside.csv"
        f.rename(target)
        f.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "unexpected legacy shard members"):
            audit(self.root, OLD, NEW)

    def test_invalid_epoch_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid source epoch SHA"):
            audit(self.root, "bad", NEW)


if __name__ == "__main__":
    unittest.main()
