"""Same-commit checkpoint selection must fail closed on epochs and contents."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collector.p1_active_migration_checkpoint import resolve

SHA = "a"*64

class MigrationCheckpointTests(unittest.TestCase):
    def test_selects_epoch_from_validated_lock(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/"evidence/checkpoints").mkdir(parents=True)
            (root/"evidence/p1_active_roster.json").write_text(json.dumps({"source_sha256": SHA}))
            (root/("evidence/checkpoints/"+SHA+".json")).write_text(json.dumps({
                "source_sha256": SHA, "completed_shards": 2,
                "completed_issuers": 16, "shard_count": 400}))
            with patch("collector.p1_active_migration_checkpoint.unpack", return_value=(b"csv", {})), patch(
                "collector.p1_active_migration_checkpoint.validate", side_effect=lambda x:x):
                data = resolve(root)
            self.assertEqual(data["completed_shards"], 2)
            self.assertEqual(data["source_sha256"], SHA)
            self.assertFalse(data["writer_cutover_authorized"])

    def test_rejects_mixed_epoch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/"evidence/checkpoints").mkdir(parents=True)
            (root/"evidence/p1_active_roster.json").write_text(json.dumps({"source_sha256": SHA}))
            (root/("evidence/checkpoints/"+SHA+".json")).write_text(json.dumps({
                "source_sha256": "b"*64, "completed_shards": 2,
                "completed_issuers": 16, "shard_count": 400}))
            with patch("collector.p1_active_migration_checkpoint.unpack", return_value=(b"csv", {})), patch(
                "collector.p1_active_migration_checkpoint.validate", side_effect=lambda x:x):
                with self.assertRaises(ValueError):
                    resolve(root)

    def test_missing_checkpoint_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"evidence").mkdir()
            (root/"evidence/p1_active_roster.json").write_text(json.dumps({"source_sha256": SHA}))
            with patch("collector.p1_active_migration_checkpoint.unpack",return_value=(b"csv",{})):
                with self.assertRaises(FileNotFoundError):
                    resolve(root)

if __name__=="__main__":
    unittest.main()
