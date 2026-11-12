"""Schedule creation delay and final proof of actual accepted P1 shard."""
import copy
import json
import unittest
from datetime import datetime,timezone
from pathlib import Path
from collector.p1_schedule_latency_durable_yield import review

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,12,5,55,tzinfo=timezone.utc)
def fixture():
    receipt=json.loads((ROOT/"evidence/schedule_runs/5ba00fbd720fad90/run_43119727655_attempt_1.json").read_text())
    ledger=json.loads((ROOT/"evidence/checkpoints/5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022.json").read_text())
    run={
        "id":43119727655,
        "name":"P1 origin 10 17 * * 0-4 [NO TRADES]",
        "path":".github/workflows/p1-fresh-vendor-roster.yml",
        "head_branch":"main","event":"schedule",
        "created_at":"2026-11-11T23:25:37Z",
        "status":"completed","conclusion":"success",
        "head_sha":receipt["head_sha"],"run_attempt":1,
    }
    return [{"total_count":1,"workflow_runs":[run]},{"43119727655":receipt},ledger]
class LatencyYieldTests(unittest.TestCase):
    def setUp(self):
        self.args=copy.deepcopy(fixture())
    def reject(self):
        with self.assertRaises(ValueError):
            review(*self.args,NOW)
    def test_real_last_run_one_sha_verified_shard(self):
        result=review(*self.args,NOW)
        self.assertEqual(result["recent_24h_scheduled_runs"],1)
        self.assertEqual(result["scheduled_runs_with_final_sha_attestation"],1)
        self.assertEqual(result["final_verified_source_run_shards_sample_total"],1)
        self.assertEqual(result["runs"][0]["validated_source_shard_indices"],[377])
        self.assertEqual(result["runs"][0]["scheduled_creation_lag_minutes"],375.617)
        self.assertEqual(result["scheduled_creation_lag_bucket_counts"]["SEVERE_OVER_3H"],1)
        self.assertTrue(result["not_derived_as_new_since_current_checkpoint"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_source_receipt_unavailable_not_a_zero_yield_claim(self):
        self.args[1]={}
        result=review(*self.args,NOW)
        self.assertEqual(result["unattested_scheduled_runs"],1)
        self.assertIsNone(result["runs"][0]["sampled_original_shards_accepted"])
        self.assertEqual(result["final_verified_source_run_shards_sample_total"],0)
    def test_mismatched_run_head_sha_rejected(self):
        self.args[0]["workflow_runs"][0]["head_sha"]="a"*40
        self.reject()
    def test_wrong_final_conclusion_rejected_from_sha_attestation(self):
        self.args[0]["workflow_runs"][0]["conclusion"]="failure"
        result=review(*self.args,NOW)
        self.assertEqual(result["scheduled_runs_with_final_sha_attestation"],0)
        self.assertEqual(result["unattested_scheduled_runs"],1)
    def test_unrelated_workflow_rejected(self):
        self.args[0]["workflow_runs"][0]["path"]="other/workflow.yml"
        self.reject()
    def test_forged_cron_rejected(self):
        self.args[0]["workflow_runs"][0]["name"]="P1 origin 10 22 * * 1-5 [NO TRADES]"
        self.reject()
    def test_duplicate_runs_rejected(self):
        self.args[0]["workflow_runs"].append(copy.deepcopy(self.args[0]["workflow_runs"][0]))
        self.args[0]["total_count"]=2
        self.reject()
    def test_different_receipt_run_rejected(self):
        self.args[1]["43119727655"]["run_id"]=111
        self.reject()
    def test_source_epoch_mismatch_rejected(self):
        self.args[2]["source_sha256"]="a"*64
        self.reject()
    def test_original_manifest_sha_tamper_rejected(self):
        self.args[1]["43119727655"]["new_archived_shard_evidence"][0]["manifest_sha256"]="a"*64
        self.reject()
    def test_nonselected_receipt_rejected(self):
        self.args[1]["111"]=copy.deepcopy(self.args[1]["43119727655"])
        self.reject()
    def test_old_runs_outside_window(self):
        result=review(*self.args,datetime(2026,11,14,5,55,tzinfo=timezone.utc))
        self.assertEqual(result["recent_24h_workflow_runs"],0)
        self.assertEqual(result["final_verified_source_run_shards_sample_total"],0)
    def test_live_queued_run_must_not_certify_final_acceptance(self):
        self.args[0]["workflow_runs"][0]["status"]="in_progress"
        self.args[0]["workflow_runs"][0]["conclusion"]=None
        result=review(*self.args,NOW)
        self.assertEqual(result["scheduled_runs_with_final_sha_attestation"],0)
    def test_suspicious_future_run_rejected(self):
        self.args[0]["workflow_runs"][0]["created_at"]="2026-11-14T05:00:00Z"
        self.reject()
