"""Exercise the readback failure paths without touching any durable Git branch."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from collector.p2_durable_catchup_readback import _pin, verify


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.epoch = "a" * 64
        segment = self.epoch[:16]
        self.source, self.archive, self.previous, self.current = (
            root / name for name in ("source", "archive", "previous", "current")
        )
        (self.source / "evidence/checkpoints").mkdir(parents=True)
        self.write(self.source / "evidence/checkpoints" / f"{self.epoch}.json", {})
        self.prior_summary = dict(source_epoch_sha256=self.epoch)
        self.summary = dict(self.prior_summary, status="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
                            feature_complete_shards=270, observed_archived_shards=289,
                            issuer_evidence_gap_count=20)
        self.replay = dict(source_epoch_sha256=self.epoch, selection_method="PRIORITIZE_UNOBSERVED_ACROSS_PAGES",
                           selected_shards=["shard_0342"], computed_feature_issuers=8)
        for scope, summary in ((self.previous, self.prior_summary), (self.current, self.summary)):
            (scope / "summaries").mkdir(parents=True)
            self.write(scope / "summaries" / f"{segment}.json", summary)
            (scope / "reports" / segment).mkdir(parents=True)
            self.write(scope / "reports" / segment / "10.json", {"old": True})
        self.summary_path = self.current / "summaries" / f"{segment}.json"
        self.reports = self.current / "reports" / segment
        self.write(self.reports / "11.json", self.replay)
        pkg = "collector.p2_durable_catchup_readback."
        self.enterContext(patch(pkg + "_pin"))
        self.run = self.enterContext(patch(pkg + "run", return_value=self.replay))
        self.summarize = self.enterContext(patch(pkg + "summarize", return_value=self.summary))

    @staticmethod
    def write(path, data):
        path.write_text(json.dumps(data))

    def check(self):
        return verify(self.source, self.archive, self.previous, self.current,
                      source_sha="1" * 40, archive_sha="2" * 40, previous_sha="3" * 40,
                      current_sha="4" * 40, epoch=self.epoch, receipt_id="11")

    def test_success_preserves_research_boundary(self):
        out = self.check()
        self.assertEqual((out["selected_shards"], out["computed_features"]), (["shard_0342"], 8))
        self.assertEqual((out["trade_gate"], out["orders"]), ("BLOCKED", []))
        self.assertIs(out["historical_PIT_verified"], False)

    def test_existing_receipt_changed_even_if_json_is_equal(self):
        old = self.reports / "10.json"
        old.write_bytes(old.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "unchanged durable originals"):
            self.check()
        self.run.assert_not_called()

    def test_deleted_existing_receipt_or_unrelated_extra_receipt(self):
        for action in ("deleted", "extra"):
            with self.subTest(action=action):
                if action == "deleted":
                    (self.reports / "10.json").unlink()
                else:
                    self.write(self.reports / "10.json", {"old": True})
                    self.write(self.reports / "12.json", {})
                with self.assertRaisesRegex(ValueError, "exactly one added"):
                    self.check()

    def test_stored_catchup_page_does_not_match_independent_replay(self):
        self.write(self.reports / "11.json", {**self.replay, "computed_feature_issuers": 7})
        with self.assertRaisesRegex(ValueError, "does not independently reproduce"):
            self.check()
        self.summarize.assert_not_called()

    def test_stale_summary_rejected_even_if_page_replays(self):
        self.write(self.summary_path, {**self.summary, "feature_complete_shards": 269})
        with self.assertRaisesRegex(ValueError, "summary does not reproduce"):
            self.check()

    def test_cross_epoch_rejected_before_replay(self):
        self.write(self.summary_path, {**self.summary, "source_epoch_sha256": "f" * 64})
        with self.assertRaisesRegex(ValueError, "different epoch"):
            self.check()
        self.run.assert_not_called()

    def test_checkout_pin_rejects_mismatched_head_and_dirty_tree(self):
        sha = "1" * 40
        for responses in ((b"2" * 40,), (sha.encode(), b"?? extra.json")):
            with self.subTest(responses=responses), patch(
                "collector.p2_durable_catchup_readback.subprocess.check_output", side_effect=responses
            ), self.assertRaisesRegex(ValueError, "clean pinned Git tree"):
                _pin(self.source, sha)
