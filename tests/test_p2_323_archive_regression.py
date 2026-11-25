"""Regression against immutable 311- and 323-shard research snapshots."""
import hashlib
import json
import os
from pathlib import Path
import unittest

from collector.p1_active_migration_checkpoint import resolve
from collector.p2_coverage_display import summarize
from collector.p2_gap_disposition import compare
from collector.p2_original_gap_window_triage import check_current_checkpoint, diagnose


def load(path):
    return json.loads(path.read_bytes())


@unittest.skipUnless(os.getenv("P2_SNAPSHOT_ROOT"), "requires pinned Git worktrees")
class P2Archive323Regression(unittest.TestCase):
    def test_new_gap_stays_in_review_and_new_archives_match_their_receipts(self):
        root = Path(os.environ["P2_SNAPSHOT_ROOT"])
        lock = resolve(root / "checkpoint")
        epoch = lock["source_sha256"][:16]
        archive = root / "archive" / epoch
        status = load(archive / "archive_status.json")
        checkpoint = load(root / "checkpoint" / lock["checkpoint_path"])
        current = load(root / "coverage" / "summaries" / f"{epoch}.json")
        previous = load(root / "previous" / "summaries" / f"{epoch}.json")
        witness = check_current_checkpoint(current, checkpoint, status)
        self.assertEqual(witness["checkpoint_completed_shards"], 323)
        self.assertEqual(witness["checkpoint_completed_issuers"], 2578)
        with self.assertRaisesRegex(ValueError, "stale or unsafe P2 coverage"):
            check_current_checkpoint(previous, checkpoint, status)

        current_ids, old_ids = map(set, (current["observed_shard_ids"], previous["observed_shard_ids"]))
        self.assertEqual(current_ids, {f"shard_{i:04d}" for i in status["archived_shards"]})
        self.assertLess(old_ids, current_ids)
        added = current_ids - old_ids
        self.assertEqual(added, {f"shard_{i:04d}" for i in (*range(240, 245), *range(322, 329))})
        self.assertEqual(set(current["gap_shard_ids"]) - set(previous["gap_shard_ids"]), {"shard_0324"})
        self.assertEqual(set(current["gap_issuer_codes"]) - set(previous["gap_issuer_codes"]), {"sz.002388"})

        verified = set()
        for shard in sorted(added):
            folder = archive / shard
            receipt = load(folder / "quality.json")
            self.assertEqual(len(receipt["results"]), 8)
            for row in receipt["results"]:
                code = row["code"]
                self.assertNotIn(code, verified)
                verified.add(code)
                raw = (folder / f"{code.replace('.', '_')}.csv").read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"], code)
        self.assertEqual(len(verified), 96)

        replay = diagnose(current, archive)
        gap = next(r for r in replay["results"] if r["issuer"] == "sz.002388")
        self.assertEqual(gap["diagnosis"], "VENDOR_MARKED_NOT_TRADABLE_AT_ASOF")
        self.assertEqual(gap["trailing_vendor_suspended_rows"], 9)
        self.assertIs(gap["official_halt_explanation_authenticated"], False)
        pin = Path(__file__).resolve().parents[1] / "manifests/p2_gap_explanations_20261020.json"
        current_pin = load(pin)
        new_entry = current_pin["entries"]["sz.002388"]
        # Preserve the regression for recognizing an unexplained issuer before the pin is updated.
        previous_pin = {**current_pin, "entries": {
            k: v for k, v in current_pin["entries"].items() if k != "sz.002388"
        }}
        before = compare(replay, previous_pin)
        self.assertEqual(before["review_reason_counts"], {"NEW_GAP_NOT_IN_PIN": 1})
        self.assertEqual([r["issuer"] for r in before["review_queue"]], ["sz.002388"])
        self.assertEqual(before["explained_feature_unavailable"], 22)

        self.assertLessEqual(new_entry["halt_effective_session"], gap["asof_date"])
        self.assertGreater(new_entry["retrospective_only_resume"]["session"], gap["asof_date"])
        self.assertTrue(all("/2026-10-08/" in url for url in new_entry["source_urls"]))
        result = compare(replay, current_pin)
        self.assertEqual(result["review_required"], 0)
        self.assertEqual(result["explained_feature_unavailable"], 23)
        self.assertEqual(next(r["reason"] for r in result["rows"] if r["issuer"] == "sz.002388"),
                         "HALTED_AT_CUTOFF")
        self.assertEqual(result["feature_gaps_resolved"], 0)
        self.assertEqual(result["orders"], [])
        display = summarize(current, result)
        self.assertEqual(display["feature_complete_shards"], {"count": 301, "total": 323, "percent": 93.19})
        self.assertEqual(display["computed_feature_issuers"]["count"], 2555)
        self.assertEqual(current["feature_issuer_count"] - previous["feature_issuer_count"], 95)
        self.assertEqual(display["trade_gate"], "BLOCKED")
        self.assertIs(display["historical_PIT_verified"], False)
