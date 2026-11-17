from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from collector.p1_checkpoint import epoch_path
from collector.p1_fresh_shard_plan import plan
from collector.p1_gap_batch_queue import queue, tracked_states
from collector.p1_quad_pick import choose_gap_window
from collector.p1_roster_lock import unpack


class GapQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(__file__).resolve().parents[1]
        lock = json.loads((base / "evidence/p1_active_roster.json").read_bytes())
        cls.ledger = json.loads((base / epoch_path(lock["source_sha256"])).read_bytes())
        raw, receipt = unpack(lock)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "roster.csv"
            source.write_bytes(raw)
            cls.plan = plan(source, root / "shards", receipt["requested_day"])
        cls.ids = [r["index"] for r in cls.ledger["completed"]]
        cls.status = dict(source_sha256=lock["source_sha256"], trade_gate="BLOCKED", archived_shards=cls.ids)

    def test_exact_once_and_current_picker_compatibility(self):
        report = queue(self.plan, self.ledger, self.status, self.ids)
        self.assertEqual([i for b in report["batches"] for i in b["shard_indices"]],
                         self.ledger["pending_shards"])
        for batch in report["batches"]:
            preview = batch["dispatch_preview"]
            self.assertEqual(choose_gap_window(self.plan, self.ledger, preview["gap_window"],
                                               int(preview["shards_per_run"])), batch["shard_indices"])
        self.assertFalse(report["permission_to_write_or_trade"])
        self.assertFalse(report["archive_original_csvs_replayed"])

    def test_missing_directory_rejected(self):
        with self.assertRaisesRegex(ValueError, "Git shard directories"):
            queue(self.plan, self.ledger, self.status, self.ids[1:])

    def test_checkpoint_and_index_disagreement_rejected(self):
        ids = self.ids[1:]
        with self.assertRaisesRegex(ValueError, "archive/checkpoint"):
            queue(self.plan, self.ledger, dict(self.status, archived_shards=ids), ids)

    def test_probe_only_does_not_become_archived(self):
        probe = Path("tests/fixtures/p1/probe_run_43820286717.json").read_bytes()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for row in json.loads(probe)["verified"]:
                name = self.plan["shards"][row["index"]]["name"]
                (root / name).write_text("\n".join(row["csv_sha256_by_issuer"]) + "\n")
            result = tracked_states(self.plan, [232, 238], root, [231, 232, 238], probe)
            self.assertEqual([r["status"] for r in result], [
                "ARCHIVED_IN_PINNED_SNAPSHOT", "PREPROBED_NOT_ARCHIVED",
                "PENDING_NO_MATCH_IN_PINNED_PROBE",
            ])
            with self.assertRaisesRegex(ValueError, "probe bytes"):
                tracked_states(self.plan, [232], root, [232], probe + b"x")
