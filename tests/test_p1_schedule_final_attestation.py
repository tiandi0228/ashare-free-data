"""Post-run P1 schedule attestation must not confuse start, success, archive."""
import copy
import json
import unittest
from unittest.mock import patch

from collector.p1_schedule_run_provenance import build as source_build
from collector.p1_schedule_final_attestation import (
    base, locate_schedule_receipt, verify, run_review
)

EPOCH = "a"*64
SHA = "b"*40
CRON = "10 3 * * 1-5"


def run(*, event="schedule", conclusion="success", created="2026-11-05T03:35:00Z"):
    return {
        "id": 123456, "run_attempt": 1,
        "head_sha": SHA, "head_branch": "main",
        "path": ".github/workflows/p1-fresh-vendor-roster.yml",
        "event": event, "created_at": created,
        "status": "completed", "conclusion": conclusion,
    }


def progress():
    return {
        "phase": "P1_READ_ONLY_RUN_PROGRESS", "status": "DURABLE_PROGRESS",
        "source_sha256": EPOCH,
        "previous_shards": 0, "current_shards": 2,
        "new_shards_durably_accepted": 2,
        "new_shard_count": 2,
        "new_selected_shards": [2, 3],
        "effective_shard_count": 2,
        "trade_gate": "BLOCKED", "historical_PIT_verified": False,
        "archive_csv_replay_enabled": True, "archive_gap_issuers": 0,
        "orders": [], "executable_candidates": []
    }


def source():
    return source_build(
        run(), progress(), cron=CRON, run_id=123456, attempt=1,
        sha=SHA, actual_requested_shards=2
    )


def checkpoint():
    return {
        "phase": "P1_ROSTER_SHARD_LEDGER",
        "source_sha256": EPOCH,
        "shard_count": 4,
        "completed": [
            {"index": i, "issuer_count": 8,
             "manifest_sha256": "c"*64, "receipt_sha256": "d"*64}
            for i in [2, 3]
        ],
        "completed_shards": 2, "completed_issuers": 16,
        "pending_shards": [0, 1], "next_shard": 0,
        "failed_in_this_reconciliation": [],
        "full_market_bars_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [],
        "executable_candidates": [],
    }


class P1ScheduleFinalTests(unittest.TestCase):
    def test_valid_final_success_has_only_research_proof(self):
        result = verify(run(), source(), checkpoint())
        self.assertEqual(result["state"],
                         "SCHEDULE_SUCCESS_AND_DURABLE_SHARDS_CONFIRMED")
        self.assertEqual(result["literal_cron_utc"], CRON)
        self.assertEqual(result["inferred_nominal_slot_beijing"],
                         "2026-11-05T11:10:00+08:00")
        self.assertEqual(result["github_creation_delay_minutes"], 25)
        self.assertEqual(result["accepted_source_shard_indices"], [2, 3])
        self.assertTrue(result["final_actions_success_authenticated"])
        self.assertTrue(result["scheduled_cron_origin_authenticated"])
        self.assertTrue(result["durable_same_epoch_shard_inclusion_verified"])
        self.assertFalse(result["inferred_nominal_slot_date_authenticated"])
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertFalse(result["trade_authorized"])
        self.assertEqual(result["orders"], [])
        self.assertTrue(json.dumps(result))

    def test_push_and_manual_must_not_be_counted_as_scheduled(self):
        for event in ("push", "workflow_dispatch", "pull_request"):
            with self.subTest(event=event):
                result = verify(run(event=event))
                self.assertEqual(result["state"], "NOT_SCHEDULED_RUN")
                self.assertFalse(result["final_actions_success_authenticated"])

    def test_missing_receipt_not_mislabeled_success(self):
        r = verify(run(), None, None)
        self.assertEqual(r["state"], "SCHEDULE_RECEIPT_MISSING_NOT_PROVEN")
        self.assertFalse(r["scheduled_cron_origin_authenticated"])

    def test_failed_workflow_does_not_erase_read_only_archive_inclusion(self):
        report = verify(run(conclusion="failure"), source(), checkpoint())
        self.assertEqual(report["state"],
                         "SCHEDULE_FINAL_FAILURE_OR_OTHER_CONCLUSION")
        self.assertFalse(report["final_actions_success_authenticated"])
        self.assertTrue(report["durable_same_epoch_shard_inclusion_verified"])
        self.assertEqual(report["trade_gate"], "BLOCKED")

    def test_unfinished_actions_cannot_self_certify(self):
        in_flight = run()
        in_flight.update(status="in_progress", conclusion=None)
        result = verify(in_flight, source(), checkpoint())
        self.assertEqual(result["state"], "FINAL_ACTIONS_CONCLUSION_NOT_AVAILABLE")
        self.assertFalse(result["final_actions_success_authenticated"])

    def test_checkpoint_missing_has_no_final_success_claim(self):
        result = verify(run(), source())
        self.assertEqual(result["state"],
                         "PERMANENT_CHECKPOINT_UNAVAILABLE_NO_CERTIFICATION")
        self.assertFalse(result["final_actions_success_authenticated"])

    def test_immutable_source_has_to_match_github_identity(self):
        variants = [
            {"run_id": 321},
            {"run_attempt": 2},
            {"head_sha": "e"*40},
            {"trigger": "workflow_dispatch"},
            {"phase": "WRONG"},
            {"trade_gate": "OPEN"},
            {"historical_PIT_verified": True},
            {"orders": [{"side": "BUY"}]},
            {"trade_authorized": True},
            {"archive_csv_replay_enabled": False},
            {"github_workflow_conclusion_authenticated": True},
            {"nominal_slot_date_is_inferred_not_authenticated": False},
            {"actual_scheduled_execution_is_proven": False},
            {"trigger_cron_utc": "10 1 * * 1-5"},
            {"github_queue_creation_delay_minutes": 0},
            {"nominal_slot_beijing": "2026-11-05T13:10:00+08:00"},
            {"new_original_shard_indices": [2, 2]},
            {"shards_durably_accepted_by_run": 3},
            {"checkpoint_shards_after": 3},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                receipt = source()
                receipt.update(variant)
                with self.assertRaises(ValueError):
                    verify(run(), receipt, checkpoint())

    def test_checkpoint_wrong_epoch_tamper_and_missing_index_refuse(self):
        variants = [
            {"source_sha256": "e"*64},
            {"completed_shards": 1},
            {"completed": [
                {"index": 0, "issuer_count": 8, "manifest_sha256": "c"*64,
                 "receipt_sha256": "d"*64},
                {"index": 3, "issuer_count": 8, "manifest_sha256": "c"*64,
                 "receipt_sha256": "d"*64}
            ], "pending_shards": [1, 2], "next_shard": 1},
            {"trade_gate": "OPEN"},
            {"historical_PIT_verified": True},
        ]
        for v in variants:
            with self.subTest(variant=v):
                cp = checkpoint()
                cp.update(copy.deepcopy(v))
                with self.assertRaises(ValueError):
                    verify(run(), source(), cp)

    def test_no_new_shard_is_not_progress(self):
        record = source()
        record.update(
            shards_durably_accepted_by_run=0,
            checkpoint_shards_before=2,
            checkpoint_shards_after=2,
            new_original_shard_indices=[],
        )
        result = verify(run(), record, checkpoint())
        self.assertEqual(result["state"], "SCHEDULE_SUCCESS_NO_NEW_ARCHIVED_SHARDS")
        self.assertEqual(result["durably_accepted_shards_in_source_run"], 0)
        self.assertTrue(result["final_actions_success_authenticated"])

    def test_wrong_run_workflow_is_rejected(self):
        for variant in [
            {"head_branch": "feature"},
            {"path": ".github/workflows/p4-real-ma20-forward-observation.yml"},
            {"head_sha": "x"*40},
            {"run_attempt": "1"},
            {"conclusion": "mysterious"},
        ]:
            with self.subTest(variant=variant):
                bad = run()
                bad.update(variant)
                with self.assertRaises(ValueError):
                    verify(bad, source(), checkpoint())

    @patch("collector.p1_schedule_final_attestation.gh")
    def test_non_schedule_review_needs_no_archive_lookup(self, mock):
        mock.return_value = json.dumps(run(event="push"))
        report = run_review("org/repo", 123456)
        self.assertEqual(report["state"], "NOT_SCHEDULED_RUN")
        self.assertEqual(mock.call_count, 1)

    @patch("collector.p1_schedule_final_attestation.gh")
    def test_no_schedule_directory_is_unproven_not_failed_archive(self, mock):
        import subprocess
        def fake(*args):
            if "schedule_runs" in args[0]:
                raise subprocess.CalledProcessError(
                    1, args, stderr="HTTP 404 Not Found")
            return json.dumps(run())
        mock.side_effect = fake
        result = run_review("org/repo", 123456)
        self.assertEqual(result["state"], "SCHEDULE_RECEIPT_MISSING_NOT_PROVEN")

    @patch("collector.p1_schedule_final_attestation.gh")
    def test_api_error_is_not_construed_as_no_receipt(self, mock):
        import subprocess
        def fake(*args):
            if "schedule_runs" in args[0]:
                raise subprocess.CalledProcessError(
                    1, args, stderr="HTTP 403 Forbidden")
            return json.dumps(run())
        mock.side_effect = fake
        with self.assertRaises(subprocess.CalledProcessError):
            run_review("org/repo", 123456)


if __name__ == "__main__":
    unittest.main()
