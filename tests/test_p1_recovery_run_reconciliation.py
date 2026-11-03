"""Do not conflate a successful workflow with proven historical shard recovery."""
import datetime as dt,unittest
from collector.p1_recovery_run_reconciliation import reconcile,PHASE
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Shanghai")
NOW=dt.datetime(2026,11,3,15,0,tzinfo=TZ)
ORIGIN={"id":100,"created_at":"2026-11-03T06:20:00Z"}
def attempt():
    return {"phase":"P1_SINGLE_SHARD_DISPATCH_ATTEMPT",
            "state":"DISPATCH_ATTEMPT_RESERVED",
            "origin_check_run_id":100,"slot":"2026-11-03T13:10:00+08:00",
            "requested_shards":1,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
def run(id=200,created="2026-11-03T06:25:00Z",event="workflow_dispatch",
        status="completed",conclusion="success"):
    return {"id":id,"created_at":created,"event":event,
            "status":status,"conclusion":conclusion,
            "path":".github/workflows/p1-fresh-vendor-roster.yml"}
class ReconciliationTests(unittest.TestCase):
    def test_success_still_unattributed(self):
        r=reconcile(attempt(),[run()],NOW,original_run=ORIGIN)
        self.assertEqual(r["state"],"CANDIDATE_RUN_SUCCESS_UNATTRIBUTED")
        self.assertFalse(r["causal_dispatch_link_verified"])
        self.assertFalse(r["historical_collection_verified"])
        self.assertEqual(r["verified_new_shards"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_push_or_unrelated_run_not_candidate(self):
        r=reconcile(attempt(),[run(event="push")],NOW,original_run=ORIGIN)
        self.assertEqual(r["state"],"NO_DISPATCH_RUN_OBSERVED")
        self.assertEqual(r["candidate_runs"],[])
    def test_multiple_candidates_ambiguous(self):
        r=reconcile(attempt(),[run(),run(id=201,created="2026-11-03T06:27:00Z")],
                    NOW,original_run=ORIGIN)
        self.assertEqual(r["state"],"MULTIPLE_RUNS_ATTRIBUTION_AMBIGUOUS")
        self.assertEqual(len(r["candidate_runs"]),2)
    def test_failed_and_pending_distinguished(self):
        self.assertEqual(reconcile(attempt(),[run(conclusion="failure")],
                         NOW,original_run=ORIGIN)["state"],
                         "CANDIDATE_RUN_NOT_SUCCESSFUL")
        self.assertEqual(reconcile(attempt(),[run(status="in_progress",conclusion=None)],
                         NOW,original_run=ORIGIN)["state"],
                         "CANDIDATE_RUN_PENDING")
    def test_future_or_old_candidates_excluded(self):
        for created in ("2026-11-03T06:19:59Z","2026-11-03T06:36:00Z"):
            with self.subTest(created=created):
                r=reconcile(attempt(),[run(created=created)],NOW,original_run=ORIGIN)
                self.assertEqual(r["candidate_runs"],[])
    def test_forged_source_and_wrong_origin_block(self):
        x=attempt();x["trade_gate"]="OPEN"
        self.assertEqual(reconcile(x,[run()],NOW,original_run=ORIGIN)["state"],
                         "INVALID_DISPATCH_ATTEMPT")
        self.assertEqual(reconcile(attempt(),[run()],NOW,
                         original_run={"id":999,"created_at":ORIGIN["created_at"]})["state"],
                         "ORIGIN_ID_MISMATCH")
    def test_no_claim_or_unknown_api_never_verifies(self):
        self.assertEqual(reconcile({},[run()],NOW,original_run=ORIGIN)["state"],
                         "NO_VALID_DISPATCH_ATTEMPT")
        self.assertEqual(reconcile(attempt(),None,NOW,original_run=ORIGIN)["state"],
                         "RUN_HISTORY_UNKNOWN")
if __name__=="__main__":unittest.main()
