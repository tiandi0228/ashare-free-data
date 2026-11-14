"""P1 latest workflow runs do not imply durable ingestion deltas."""
import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from collector.p1_live_schedule_archive_health import audit, TARGET, WORKFLOW_NAME

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,12,12,0,tzinfo=timezone.utc)
def fixture():
    lock=json.loads((ROOT/"evidence/p1_active_roster.json").read_text())
    ledger=json.loads((ROOT/"evidence/checkpoints/5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022.json").read_text())
    archive=json.loads((ROOT/"archived-research/5ba00fbd720fad90/archive_status.json").read_text())
    def run(rid,when,status="completed",conclusion="success",event="schedule"):
        return {"id":rid,"name":WORKFLOW_NAME,"path":TARGET,
                "head_branch":"main","event":event,"created_at":when,
                "status":status,"conclusion":conclusion}
    runs={"total_count":1001,"workflow_runs":[
        run(23,"2026-11-12T11:10:00Z"),
        run(22,"2026-11-12T10:10:00Z","in_progress",None),
        run(21,"2026-11-11T09:10:00Z","completed","failure")]}
    return [lock,ledger,archive,runs]
class RunHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=fixture()
    def setUp(self):
        self.args=copy.deepcopy(self.original)
    def reject(self):
        with self.assertRaises(ValueError):audit(*self.args,NOW)
    def test_same_epoch_and_recent_status_without_fabricated_delta(self):
        r=audit(*self.args,NOW)
        self.assertEqual(r["active_completed_shards"],241)
        self.assertEqual(r["active_total_shards"],400)
        self.assertEqual(r["remaining_shards"],159)
        self.assertEqual(r["recent_24h_runs"],2)
        self.assertEqual(r["recent_24h_successful_runs"],1)
        self.assertEqual(r["active_or_queued_run_ids"],[22])
        self.assertEqual(r["last_actions_run"]["run_id"],23)
        self.assertIsNone(r["new_shards_from_run_history"])
        self.assertIsNone(r["new_shards_since_current_checkpoint"])
        self.assertFalse(r["run_list_complete"])
        self.assertFalse(r["recovery_dispatch_authorized"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_wrong_source_epoch_rejected(self):
        self.args[1]["source_sha256"]="a"*64
        self.reject()
    def test_archive_membership_changed_rejected(self):
        self.args[2]["archived_shards"][0]=400
        self.reject()
    def test_missing_archive_shard_rejected(self):
        self.args[2]["archived_shards"].pop()
        self.reject()
    def test_real_scheduled_custom_run_name_accepted(self):
        self.args[3]["workflow_runs"][0]["name"]="P1 origin 10 17 * * 0-4 [NO TRADES]"
        r=audit(*self.args,NOW)
        self.assertEqual(r["last_actions_run"]["run_id"],23)
        self.assertIsNone(r["new_shards_from_run_history"])

    def test_forged_cron_title_rejected(self):
        self.args[3]["workflow_runs"][0]["name"]="P1 origin 10 16 * * 1-5 [NO TRADES]"
        self.reject()

    def test_manual_run_name_accepted(self):
        self.args[3]["workflow_runs"][0]["event"]="workflow_dispatch"
        self.args[3]["workflow_runs"][0]["name"]="P1 origin workflow_dispatch [NO TRADES]"
        r=audit(*self.args,NOW)
        self.assertEqual(r["recent_24h_successful_runs"],1)
        self.assertIsNone(r["new_shards_from_run_history"])

    def test_wrong_workflow_name_rejected(self):
        self.args[3]["workflow_runs"][0]["name"]="Other workflow"
        self.reject()
    def test_wrong_branch_rejected(self):
        self.args[3]["workflow_runs"][0]["head_branch"]="other"
        self.reject()
    def test_unknown_trigger_rejected(self):
        self.args[3]["workflow_runs"][0]["event"]="pull_request"
        self.reject()
    def test_duplicate_run_ids_rejected(self):
        self.args[3]["workflow_runs"][1]["id"]=23
        self.reject()
    def test_future_run_rejected(self):
        self.args[3]["workflow_runs"][0]["created_at"]="2026-11-13T11:10:00Z"
        self.reject()
    def test_active_run_claiming_success_rejected(self):
        self.args[3]["workflow_runs"][1]["conclusion"]="success"
        self.reject()
    def test_success_without_duration_is_still_no_delta(self):
        self.args[3]["workflow_runs"][1]["status"]="completed"
        self.args[3]["workflow_runs"][1]["conclusion"]="success"
        r=audit(*self.args,NOW)
        self.assertEqual(r["recent_24h_successful_runs"],2)
        self.assertIsNone(r["new_shards_from_run_history"])
    def test_incomplete_run_listing_allowed_but_explicit(self):
        self.args[3]["total_count"]=3
        r=audit(*self.args,NOW)
        self.assertTrue(r["run_list_complete"])
        self.assertIsNone(r["new_shards_since_current_checkpoint"])
    def test_missing_run_results_rejected(self):
        self.args[3]["workflow_runs"]=None
        self.reject()
