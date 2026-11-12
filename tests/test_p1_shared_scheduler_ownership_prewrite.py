"""Staged P1 native/external scheduler ownership fence: no production writes."""
import copy
import hashlib
import json
import unittest
from collector.p1_shared_scheduler_ownership_prewrite import evaluate,EPOCH,WORKFLOW

CONTRACT_SHA="a"*40
CONTRACT={
    "phase":"P1_SHARED_SCHEDULER_OWNERSHIP_V1",
    "source_epoch_sha256":EPOCH,
    "generation":7,
    "owner":"NATIVE_ONLY",
    "effective_from_utc":"2026-11-12T00:00:00Z",
    "trade_gate":"BLOCKED",
    "orders":[],
    "executable_candidates":[],
    "allow_write_before_fence_confirmation":False
}
DIGEST=hashlib.sha256((json.dumps(CONTRACT,sort_keys=True)+"\n").encode()).hexdigest()
RUN={
    "run_created_at_utc":"2026-11-12T01:10:00Z",
    "ownership_checked_at_utc":"2026-11-12T01:11:00Z",
    "source_epoch_sha256":EPOCH,"workflow_path":WORKFLOW,
    "branch":"main","run_event":"schedule","run_id":432100001,
    "run_attempt":1,"head_sha":"b"*40,
    "observed_contract_generation":7,
    "observed_contract_blob_sha":CONTRACT_SHA,
    "observed_contract_bytes_sha256":DIGEST,
    "native_schedule_currently_enabled":True
}

class OwnershipFenceTests(unittest.TestCase):
    def setUp(self):
        self.contract=copy.deepcopy(CONTRACT)
        self.run=copy.deepcopy(RUN)
        self.sha=CONTRACT_SHA
        self.digest=DIGEST
    def check(self):
        return evaluate(self.contract,self.run,
                        contract_blob_sha=self.sha,
                        contract_bytes_sha256=self.digest)
    def blocked(self,reason):
        r=self.check()
        self.assertEqual(r["decision"],"BLOCK")
        self.assertEqual(r["reason"],reason)
        self.assertFalse(r["collector_write_authorized"])
        self.assertFalse(r["external_dispatch_authorized"])
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_native_only_research_eligibility_still_no_write(self):
        r=self.check()
        self.assertEqual(r["decision"],"NATIVE_SCHEDULED_RUN_RESEARCH_ELIGIBLE")
        self.assertTrue(r["source_write_preflight_would_pass_if_integrated"])
        self.assertFalse(r["collector_write_authorized"])
        self.assertFalse(r["production_installation_verified"])
    def test_frozen_generation_denies_new_and_old_native(self):
        self.contract["owner"]="FREEZE_ALL"
        self.blocked("CUTOVER_FREEZE_BLOCKS_ALL_P1_WRITES")
    def test_external_generation_denies_old_native(self):
        self.contract["owner"]="EXTERNAL_ONLY"
        self.blocked("EXTERNAL_OWNER_NATIVE_SOURCE_VETO")
    def test_old_run_created_before_new_generation(self):
        self.run["run_created_at_utc"]="2026-11-11T23:50:00Z"
        self.blocked("OLD_RUN_CREATED_BEFORE_ACTIVE_GENERATION")
    def test_wrong_generation_rejected(self):
        self.run["observed_contract_generation"]=6
        self.blocked("RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH")
    def test_wrong_immutable_contract_sha_rejected(self):
        self.run["observed_contract_blob_sha"]="c"*40
        self.blocked("RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH")
    def test_wrong_contract_byte_digest_rejected(self):
        self.run["observed_contract_bytes_sha256"]="d"*64
        self.blocked("RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH")
    def test_workflow_branch_mismatch_denied(self):
        self.run["branch"]="ci/dev"
        self.blocked("RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH")
    def test_manual_fallback_denied(self):
        self.run["run_event"]="workflow_dispatch"
        self.blocked("MANUAL_DISPATCH_UNAUTHORIZED_IN_NATIVE_ONLY")
    def test_cron_disabled_denied(self):
        self.run["native_schedule_currently_enabled"]=False
        self.blocked("NATIVE_CRON_ENABLED_STATUS_NOT_AUTHENTICATED")
    def test_future_source_contract_denied(self):
        self.contract["effective_from_utc"]="2026-11-13T00:00:00Z"
        self.blocked("NONCAUSAL_OWNERSHIP_TIMELINE")
    def test_unknown_owner_denied(self):
        self.contract["owner"]="BOTH"
        self.blocked("UNKNOWN_SCHEDULER_OWNER")
    def test_active_stage_cannot_authorize_trades(self):
        self.contract["trade_gate"]="OPEN"
        self.blocked("CONTRACT_SOURCE_EPOCH_OR_SAFETY_INVALID")
    def test_wrong_epoch_denied(self):
        self.contract["source_epoch_sha256"]="f"*64
        self.blocked("CONTRACT_SOURCE_EPOCH_OR_SAFETY_INVALID")
    def test_bad_utc_timestamp_denied(self):
        self.run["ownership_checked_at_utc"]="2026-11-12T01:11:00+08:00"
        self.blocked("INVALID_RUN_OR_CONTRACT_UTC_TIMESTAMP")
    def test_stale_run_older_than_2_days_denied(self):
        self.run["ownership_checked_at_utc"]="2026-11-15T02:11:00Z"
        self.blocked("STALE_RUN_CONTEXT")
    def test_same_run_old_sha_denied_even_if_same_generation(self):
        self.run["head_sha"]="not-a-sha"
        self.blocked("RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH")
