"""Offline validation of durable P1 nightly dual-shard research receipts."""
import base64
import json
import unittest
from unittest.mock import patch

from collector.p1_dual_pilot_receipt import build, persist, receipt_path


class DualPilotReceiptTests(unittest.TestCase):
    def fixtures(self):
        selection = {
            "trade_gate": "BLOCKED", "requested_shards": 2,
            "selected_shards": [13, 14], "selected_count": 2,
        }
        progress = {
            "phase": "P1_READ_ONLY_RUN_PROGRESS", "trade_gate": "BLOCKED",
            "historical_PIT_verified": False, "orders": [],
            "executable_candidates": [],
            "archive_csv_replay_enabled": True, "archive_gap_issuers": 0,
            "source_sha256": "a"*64, "status": "DURABLE_PROGRESS",
            "selected_count": 2, "previous_shards": 52,
            "current_shards": 54,
            "new_selected_shards": [13, 14],
            "new_shards_durably_accepted": 2, "new_shard_count": 2,
            "effective_shard_count": 2,
            "dual_pilot_result": "TWO_VERIFIED_SHARDS_ARCHIVED",
        }
        policy = {
            "phase": "P1_OPTIONAL_SECOND_SHARD_POLICY", "trade_gate": "BLOCKED",
            "historical_PIT_verified": False, "orders": [],
            "executable_candidates": [], "accepted_second": True,
            "effective_shard_count": 2, "second_verification_passed": True,
            "status": "SECOND_SHARD_VERIFIED",
        }
        return selection, progress, policy

    def scheduled(self, *data, **overrides):
        kw = dict(run_id=450123, attempt=1, event="schedule",
                  cron="10 15 * * 1-5")
        kw.update(overrides)
        return build(*data, **kw)

    def test_verified_two_shard_schedule_is_durable_and_no_trade(self):
        record = self.scheduled(*self.fixtures())
        self.assertEqual(record["dual_pilot_result"],
                         "TWO_VERIFIED_SHARDS_ARCHIVED")
        self.assertEqual(record["new_shards_durably_accepted"], 2)
        self.assertEqual(record["trigger"], "schedule")
        self.assertFalse(record["historical_PIT_verified"])
        self.assertEqual(record["trade_gate"], "BLOCKED")
        self.assertEqual(record["orders"], [])
        self.assertTrue(receipt_path(record).endswith(
            "/run_450123_attempt_1.json"))

    def test_manual_dual_run_distinguished_from_nightly_schedule(self):
        r = self.scheduled(*self.fixtures(), event="workflow_dispatch", cron="")
        self.assertEqual(r["trigger"], "workflow_dispatch")
        self.assertIsNone(r["trigger_cron_utc"])

    def test_failed_second_preserves_first_and_is_not_called_dual_success(self):
        selection,progress,policy = self.fixtures()
        progress.update(new_selected_shards=[13],
                        new_shards_durably_accepted=1, new_shard_count=1,
                        effective_shard_count=1,
                        dual_pilot_result="FIRST_ARCHIVED_SECOND_REJECTED",
                        current_shards=53)
        policy.update(accepted_second=False, effective_shard_count=1,
                      second_verification_passed=False,
                      status="SECOND_INVALID_PRESERVE_FIRST")
        r = self.scheduled(selection,progress,policy)
        self.assertEqual(r["new_shards_durably_accepted"],1)
        self.assertEqual(r["dual_pilot_result"],
                         "FIRST_ARCHIVED_SECOND_REJECTED")

    def test_forged_two_shard_claim_or_unsafe_gate_rejected(self):
        a,b,c=self.fixtures()
        b["new_shards_durably_accepted"]=1
        with self.assertRaisesRegex(ValueError, "inconsistent|two-shard"):
            self.scheduled(a,b,c)
        a,b,c=self.fixtures()
        c["second_verification_passed"]=False
        with self.assertRaisesRegex(ValueError, "two-shard success"):
            self.scheduled(a,b,c)
        a,b,c=self.fixtures()
        b["trade_gate"]="OPEN"
        with self.assertRaisesRegex(ValueError,"validated research-only"):
            self.scheduled(a,b,c)

    def test_claimed_growth_without_matching_checkpoint_delta_rejected(self):
        a,b,c=self.fixtures()
        b["current_shards"]=55
        with self.assertRaisesRegex(ValueError,"checkpoint delta"):
            self.scheduled(a,b,c)
        a,b,c=self.fixtures()
        b["status"]="SUCCESS_NO_NEW_SHARD"
        with self.assertRaisesRegex(ValueError,"checkpoint delta"):
            self.scheduled(a,b,c)

    def test_wrong_schedule_is_not_mislabeled_as_2310_pilot(self):
        with self.assertRaisesRegex(ValueError,"scheduled trigger"):
            self.scheduled(*self.fixtures(), cron="10 3 * * 1-5")
        with self.assertRaisesRegex(ValueError,"scheduled trigger"):
            self.scheduled(*self.fixtures(), event="push", cron="")

    def test_create_only_api_and_remote_readback(self):
        receipt=self.scheduled(*self.fixtures())
        original = base64.b64encode((json.dumps(receipt)+"\n").encode()).decode()
        responses=["{}",json.dumps({"sha":"blob_sha","content":original})]
        with patch("collector.p1_dual_pilot_receipt.gh",side_effect=responses) as api:
            path=persist("test/repo",receipt)
        self.assertEqual(api.call_count,2)
        first=api.call_args_list[0]
        self.assertEqual(first.args[:2],("-X","PUT"))
        self.assertEqual(first.args[-2:],("--input","-"))
        payload=json.loads(first.kwargs["input_data"])
        self.assertNotIn("sha",payload)
        self.assertEqual(payload["branch"],"main")
        self.assertEqual(json.loads(base64.b64decode(payload["content"])),
                         receipt)
        self.assertIn("evidence/pilot_runs/",path)

    def test_remote_readback_conflict_is_rejected(self):
        receipt=self.scheduled(*self.fixtures())
        wrong=dict(receipt,new_shards_durably_accepted=1)
        body=base64.b64encode(json.dumps(wrong).encode()).decode()
        with patch("collector.p1_dual_pilot_receipt.gh",
                   side_effect=["{}",json.dumps({
                       "sha":"blob","content":body})]):
            with self.assertRaisesRegex(ValueError,"differs"):
                persist("test/repo",receipt)

    def test_workflow_records_only_requested_dual_after_progress(self):
        from pathlib import Path
        workflow=(Path(__file__).resolve().parents[1]/
                  ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        stage=workflow.index("      - name: Report verified same-epoch P1 growth")
        persisted=workflow.index("      - name: Persist two-shard pilot evidence")
        next_stage=workflow.index("      - name: Independently classify P1 coverage")
        self.assertLess(stage,persisted)
        self.assertLess(persisted,next_stage)
        block=workflow[persisted:next_stage]
        self.assertIn("if: env.P1_REQUESTED_SHARDS == '2'",block)
        self.assertIn("P1_TRIGGER_CRON: ${{ github.event.schedule }}",block)
        self.assertIn("python -m collector.p1_dual_pilot_receipt",block)
        self.assertIn("evidence/dual_pilot_receipt.json",block)
        self.assertIn("tests.test_p1_dual_pilot_receipt",workflow)


if __name__=="__main__":
    unittest.main()
