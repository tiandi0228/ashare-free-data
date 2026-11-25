"""P1 dynamic currently pinned epoch proof; 241 is a floor, never a ceiling."""
import copy
import json
import unittest
from pathlib import Path
from collector.p1_live_dynamic_archive_delta_attestation import attest

ROOT=Path(__file__).resolve().parents[1]
def sample():
    receipt=json.loads((ROOT/"evidence/schedule_runs/5ba00fbd720fad90/run_43119727655_attempt_1.json").read_text())
    checkpoint=json.loads((ROOT/"evidence/checkpoints/5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022.json").read_text())
    archive=json.loads((ROOT/"archived-research/5ba00fbd720fad90/archive_status.json").read_text())
    run={
       "id":43119727655,"run_attempt":1,"head_sha":receipt["head_sha"],
       "head_branch":"main","path":".github/workflows/p1-fresh-vendor-roster.yml",
       "event":"schedule","created_at":"2026-11-11T23:25:37Z",
       "status":"completed","conclusion":"success"
    }
    return [run,receipt,checkpoint,archive]
class DynamicDeltaAttestationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=sample()
    def setUp(self):
        self.args=copy.deepcopy(self.base)
    def reject(self):
        with self.assertRaises(ValueError):attest(*self.args)
    def test_existing_241_run_evidence(self):
        d=attest(*self.args)
        self.assertEqual(d["live_completed_shards"],241)
        self.assertEqual(d["source_run_shard_indices"],[377])
        self.assertTrue(d["source_final_success_authenticated"])
        self.assertEqual(d["source_run_new_shards"],1)
        self.assertEqual(d["live_coverage_pct"],60.25)
        self.assertFalse(d["new_live_bytes_replayed_in_this_step"])
        self.assertEqual(d["trade_gate"],"BLOCKED")
    def test_future_242_nonoverlapping_same_epoch_progress_accepted(self):
        # A second completed original shard must be consistent in both
        # current active ledger and archive. The source run remains 240->241.
        index=376
        self.assertNotIn(index,self.args[3]["archived_shards"])
        template=copy.deepcopy(self.args[2]["completed"][0])
        template["index"]=index
        template["manifest_sha256"]="a"*64
        template["receipt_sha256"]="b"*64
        self.args[2]["completed"].append(template)
        self.args[2]["completed_shards"]+=1
        self.args[2]["completed_issuers"]+=template["issuer_count"]
        self.args[2]["pending_shards"].remove(index)
        self.args[3]["archived_shards"].append(index)
        # Fully validate actual checkpoint structure with next shard index.
        self.args[2]["next_shard"]=min(self.args[2]["pending_shards"])
        d=attest(*self.args)
        self.assertEqual(d["live_completed_shards"],242)
        self.assertEqual(d["live_coverage_pct"],60.5)
        self.assertEqual(d["shards_remaining"],158)
        self.assertEqual(d["current_checkpoint_delta_above_baseline"],1)
        self.assertEqual(d["source_run_shard_indices"],[377])
        self.assertFalse(d["historical_PIT_verified"])
    def test_checkpoint_archive_lag_rejected(self):
        self.args[3]["archived_shards"].pop()
        self.reject()
    def test_legacy_epoch_rejected(self):
        self.args[2]["source_sha256"]="f"*64
        self.reject()
    def test_duplicate_original_shard_membership_rejected(self):
        self.args[3]["archived_shards"][0]=self.args[3]["archived_shards"][1]
        self.reject()
    def test_missing_run_receipt_sha_rejected(self):
        self.args[1]["new_archived_shard_evidence"][0]["receipt_sha256"]="f"*64
        self.reject()
    def test_not_final_actions_success_rejected(self):
        self.args[0]["conclusion"]="failure"
        self.reject()
    def test_inflight_actions_rejected(self):
        self.args[0]["status"]="in_progress"
        self.args[0]["conclusion"]=None
        self.reject()
    def test_original_archive_epoch_drift_rejected(self):
        self.args[3]["source_sha256"]="e"*64
        self.reject()
    def test_forged_trade_gate_rejected(self):
        self.args[3]["trade_gate"]="OPEN"
        self.reject()
    def test_proven_run_shard_not_in_archive_rejected(self):
        self.args[3]["archived_shards"]=[
            i for i in self.args[3]["archived_shards"] if i!=377]+[376]
        self.reject()
