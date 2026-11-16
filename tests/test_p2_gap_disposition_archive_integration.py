"""Fixture-backed checks of queue behavior with verified vendor archive input."""
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from collector.p2_gap_disposition import compare
from collector.p2_original_gap_window_triage import assess, diagnose


class EmptyQueueTests(unittest.TestCase):
    def test_fully_accounted_no_gap_snapshot_is_valid(self):
        fixture = json.loads(Path("manifests/p2_gap_replay_fixture_20261020.json").read_bytes())
        fixture.update(gap_issuer_codes=[], gap_reason_counts={}, issuer_evidence_gap_count=0,
                       gap_repair_queue=[])
        pin = json.loads(Path("manifests/p2_gap_explanations_20261020.json").read_bytes())
        with TemporaryDirectory() as tmp:
            epoch = Path(tmp) / fixture["source_epoch_sha256"][:16]
            with self.assertRaisesRegex(ValueError, "missing source epoch"):
                diagnose(fixture, epoch)
            epoch.mkdir()
            report = compare(diagnose(fixture, epoch), pin)
        self.assertEqual(report["review_queue"], [])
        self.assertEqual(report["feature_gaps_resolved"], 0)
        self.assertEqual(len(report["pinned_issuers_absent_from_current_gap_list"]), 21)


@unittest.skipUnless(os.environ.get("P2_ARCHIVE_EPOCH"), "requires pinned CSV checkout")
class ArchiveQueueTests(unittest.TestCase):
    def test_real_archive_replay_with_simulated_pin_drift(self):
        fixture = json.loads(Path("manifests/p2_gap_replay_fixture_20261020.json").read_bytes())
        with patch("collector.p2_original_gap_window_triage.assess", wraps=assess) as audit:
            replay = diagnose(fixture, Path(os.environ["P2_ARCHIVE_EPOCH"]))
        called = [args.args[0].name for args in audit.call_args_list]
        expected = {row["shard_id"] for row in fixture["gap_repair_queue"]}
        self.assertEqual(set(called), expected)
        self.assertEqual(len(called), len(expected))
        self.assertEqual(len(replay["results"]), 20)
        pin = json.loads(Path("manifests/p2_gap_explanations_20261020.json").read_bytes())
        baseline = compare(replay, pin)
        self.assertEqual((baseline["explained_feature_unavailable"], baseline["review_required"]), (20, 0))

        # Simulate a baseline that never saw one gap and retained an older fingerprint for another.
        keys = sorted(r["issuer"] for r in replay["results"])
        simulate = copy.deepcopy(pin)
        del simulate["entries"][keys[0]]
        simulate["entries"][keys[1]]["original_csv_sha256"] = "0" * 64
        result = compare(replay, simulate)
        self.assertEqual((result["explained_feature_unavailable"], result["review_required"]), (18, 2))
        self.assertEqual({r["issuer"]: r["review_code"] for r in result["review_queue"]},
                         {keys[0]: "NEW_GAP_NOT_IN_PIN", keys[1]: "ORIGINAL_CSV_CHANGED"})
        self.assertEqual(result["feature_gaps_resolved"], 0)
        self.assertEqual(result["trade_gate"], "BLOCKED")
