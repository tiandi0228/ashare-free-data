import unittest
from unittest.mock import patch

from collector.p2_catchup_status import inspect


class P2CatchupTest(unittest.TestCase):
    def setUp(self):
        self.cp = {"source_sha256": "epoch", "completed": [
            {"index": 2, "issuer_count": 8}, {"index": 7, "issuer_count": 8},
            {"index": 9, "issuer_count": 8}, {"index": 10, "issuer_count": 2},
        ]}
        self.archive = dict(source_sha256="epoch", archived_shards=[2, 7, 9, 10], trade_gate="BLOCKED")
        self.p2 = dict(source_epoch_sha256="epoch", phase="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
                       status="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED", trade_gate="BLOCKED",
                       historical_PIT_verified=False, coverage_certified_for_trading=False,
                       orders=[], executable_candidates=[], actionable_buy_signals=[],
                       observed_shard_ids=["shard_0002", "shard_0007"], unobserved_shard_ids=["shard_0009"],
                       gap_shard_ids=["shard_0007"], observed_archived_shards=2,
                       observed_with_feature_gaps_shards=1, feature_complete_shards=1,
                       unobserved_archived_shards=1, archived_original_shards=3,
                       observed_feature_or_gap_issuers=16, unobserved_issuer_count=8)
        guard = patch("collector.p2_catchup_status.validate")
        self.addCleanup(guard.stop)
        self.validate = guard.start()

    def test_pending_groups_and_feature_gaps_remain_separate(self):
        result = inspect(self.p2, self.cp, self.archive)
        self.validate.assert_called_once_with(self.cp)
        self.assertEqual(result["status"], "P2_CATCHUP_PENDING")
        self.assertEqual(result["pending_shard_ids"], ["shard_0009", "shard_0010"])
        self.assertEqual(result["archived_after_coverage_snapshot_ids"], ["shard_0010"])
        self.assertEqual(result["pending_issuers"], 10)
        self.assertEqual(result["observed_shards_with_feature_gaps"], 1)
        self.assertEqual(result["orders"], [])

    def test_caught_up_does_not_imply_feature_completion(self):
        snapshot = dict(self.p2, observed_shard_ids=["shard_0002", "shard_0007", "shard_0009", "shard_0010"],
                        unobserved_shard_ids=[], observed_archived_shards=4, feature_complete_shards=3,
                        unobserved_archived_shards=0, archived_original_shards=4,
                        observed_feature_or_gap_issuers=26, unobserved_issuer_count=0)
        result = inspect(snapshot, self.cp, self.archive)
        self.assertEqual(result["status"], "P2_ARCHIVE_OBSERVATION_CAUGHT_UP")
        self.assertEqual(result["pending_shard_ids"], [])
        self.assertEqual(result["observed_shards_with_feature_gaps"], 1)
        self.assertIs(result["historical_PIT_verified"], False)

    def test_mismatched_inputs_fail_closed(self):
        for extras in ({"source_epoch_sha256": "other"}, {"orders": ["x"]},
                       {"observed_shard_ids": ["shard_0002", "shard_0002"]},
                       {"observed_shard_ids": ["shard_0002", "shard_0003"]},
                       {"unobserved_shard_ids": ["shard_0002"]},
                       {"feature_complete_shards": 2}, {"archived_original_shards": 4}):
            with self.subTest(extras=extras), self.assertRaises(ValueError):
                inspect(dict(self.p2, **extras), self.cp, self.archive)
        with self.assertRaisesRegex(ValueError, "disagree"):
            inspect(self.p2, self.cp, dict(self.archive, archived_shards=[2, 7, 9, 9, 10]))
