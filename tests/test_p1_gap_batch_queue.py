from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from collector.p1_checkpoint import epoch_path
from collector.p1_fresh_shard_plan import plan
from collector.p1_gap_batch_queue import queue, refresh_preview, tracked_states
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

    def test_refresh_removes_archived_without_substituting_other_pending_shards(self):
        report = queue(self.plan, self.ledger, self.status, self.ids)
        report["archive_original_csvs_replayed"] = True
        done = self.ids[0]
        pending = self.ledger["pending_shards"]
        epoch = self.plan["source_sha256"]
        refreshed = refresh_preview(report, [done, pending[0]], epoch)
        self.assertEqual(refreshed["already_archived_shards"], [done])
        self.assertEqual(refreshed["remaining_shards"], [pending[0]])
        self.assertEqual(refreshed["dispatch_preview"],
                         {"gap_window": f"{pending[0]}:{pending[0]}", "shards_per_run": "1"})
        self.assertIsNone(refresh_preview(report, [done], epoch)["dispatch_preview"])
        split = refresh_preview(report, [pending[0], pending[2]], epoch)
        self.assertIsNone(split["dispatch_preview"])
        self.assertTrue(split["requires_separate_windows"])
        with self.assertRaisesRegex(ValueError, "same-epoch"):
            refresh_preview(report, [done], "a" * 64)
        with self.assertRaisesRegex(ValueError, "same-epoch"):
            refresh_preview(dict(report, archive_original_csvs_replayed=False), [done], epoch)

    def test_new_probe_compares_only_archived_originals_and_reports_drift(self):
        probe = Path("tests/fixtures/p1/probe_run_44029438652.json").read_bytes()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = json.loads(probe)["verified"]
            for row in entries:
                name = self.plan["shards"][row["index"]]["name"]
                (root / name).write_text("\n".join(sorted(row["csv_sha256_by_issuer"])) + "\n")
            first = entries[0]
            hashes = first["csv_sha256_by_issuer"]
            changed = next(iter(hashes))

            def quality(index):
                self.assertEqual(index, 238)
                return dict(trade_gate="BLOCKED", issuer_count=8,
                            manifest_sha256=first["manifest_sha256"],
                            results=[dict(code=code, sha256="0" * 64 if code == changed else sha,
                                          status="OBSERVED_UNVERIFIED") for code, sha in hashes.items()])

            archived, pending = tracked_states(self.plan, [239], root, [238, 239], probe, read_quality=quality)
            self.assertEqual(archived["archive_fingerprint_comparison"]["changed_issuers"], [changed])
            self.assertEqual(archived["archive_fingerprint_comparison"]["matching_count"], 7)
            self.assertFalse(archived["archive_fingerprint_comparison"]["archive_acceptance_verified"])
            self.assertIsNone(pending["archive_fingerprint_comparison"])
