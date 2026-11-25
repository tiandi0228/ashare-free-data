"""Exercise the catch-up report against real, independently pinned P1/P2 snapshots."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from collector.p2_catchup_status import inspect
from collector.p2_original_gap_window_triage import check_current_checkpoint

SOURCE = "5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
EPOCH = SOURCE[:16]
CHECKPOINT = "fe6763fa761545dd4ca8cb950179ab8e354091b2"
ARCHIVE = "9f8b580637944e4172e8d42373174e072def49c5"
STALE = "0940259f89a742b7d226ad259e9853a2b81d7062"
CURRENT = "3f07029af2bf68aa94dd363d9851ebf6c0fff3c2"


def read(commit, path):
    return json.loads(subprocess.check_output(["git", "show", f"{commit}:{path}"], timeout=15))


@unittest.skipUnless(os.environ.get("P2_CATCHUP_ARCHIVE_REPORT"), "requires pinned Git blobs")
class RealCatchupReportTests(unittest.TestCase):
    def test_archive_lag_clears_without_promoting_feature_gaps(self):
        checkpoint = read(CHECKPOINT, f"evidence/checkpoints/{SOURCE}.json")
        archive = read(ARCHIVE, f"{EPOCH}/archive_status.json")
        old, current = (read(sha, f"summaries/{EPOCH}.json") for sha in (STALE, CURRENT))
        lag = inspect(old, checkpoint, archive)
        synced = inspect(current, checkpoint, archive)
        expected = [f"shard_{i:04d}" for i in (*range(256, 262), *range(299, 310))]

        self.assertEqual(lag["status"], "P2_CATCHUP_PENDING")
        self.assertEqual((lag["p1_archived_shards"], lag["p2_observed_shards"]), (363, 346))
        self.assertEqual(lag["pending_shard_ids"], expected)
        self.assertEqual(lag["archived_after_coverage_snapshot_ids"], expected)
        self.assertEqual(lag["pending_issuers"], 136)
        with self.assertRaisesRegex(ValueError, "stale or unsafe"):
            check_current_checkpoint(old, checkpoint, archive)

        self.assertEqual(synced["status"], "P2_ARCHIVE_OBSERVATION_CAUGHT_UP")
        self.assertEqual(synced["p2_observed_shards"], 363)
        self.assertEqual(synced["pending_shard_ids"], [])
        self.assertEqual(synced["pending_issuers"], 0)
        self.assertEqual(check_current_checkpoint(current, checkpoint, archive)["gap_issuer_count"], 23)
        self.assertEqual(current["gap_issuer_codes"], old["gap_issuer_codes"])
        self.assertEqual(synced["observed_shards_with_feature_gaps"], lag["observed_shards_with_feature_gaps"])
        self.assertEqual(current["feature_issuer_count"] - old["feature_issuer_count"], 136)
        for snapshot in (lag, synced):
            self.assertEqual(snapshot["orders"], [])
            self.assertIs(snapshot["historical_PIT_verified"], False)
            self.assertEqual(snapshot["trade_gate"], "BLOCKED")

        out = Path(os.environ["P2_CATCHUP_ARCHIVE_REPORT"])
        out.write_text(json.dumps({
            "kind": "PINNED_346_TO_363_CATCHUP_REGRESSION_NOT_LIVE_STATUS",
            "checkpoint_commit": CHECKPOINT, "archive_commit": ARCHIVE,
            "prior_coverage_commit": STALE, "current_coverage_commit": CURRENT,
            "prior_coverage": lag, "current_coverage": synced,
            "feature_issuer_gaps_unchanged": current["issuer_evidence_gap_count"],
        }, indent=2) + "\n")
