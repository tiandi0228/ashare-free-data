"""Fail-closed at-most-once P1 research dispatch tests."""
import base64,datetime as dt,json,unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from collector.p1_recovery_dispatch_once import prepare,reserve_attempt,request_once,ATTEMPT_PHASE
TZ=ZoneInfo("Asia/Shanghai")
NOW=dt.datetime(2026,11,3,14,25,tzinfo=TZ)
CLAIM="recovery-claims/2026-11-03/1310.json"
def preflight(state="PREFLIGHT_PASS_DISPATCH_NOT_ENABLED"):
    return dict(state=state,slot="2026-11-03T13:10:00+08:00",
         claim_path=CLAIM,requested_shards_if_enabled=1,
         dispatch_authorized=False,dispatch_attempted=False,
         historical_collection_executed=False,trade_gate="BLOCKED")
def runs():
    return [dict(id=1,event="schedule",status="completed",conclusion="success",
       path=".github/workflows/p1-fresh-vendor-roster.yml",
       created_at="2026-11-03T03:12:00Z")]
class RecoveryDispatchTests(unittest.TestCase):
    def test_matching_preflight_and_live_run_state(self):
        record,reason=prepare("test/repo",preflight(),NOW,runs(),1,500)
        self.assertIsNone(reason)
        self.assertEqual(record["phase"],ATTEMPT_PHASE)
        self.assertEqual(record["requested_shards"],1)
        self.assertEqual(record["attempt_path"],
                         "recovery-dispatch-attempts/2026-11-03/1310.json")
        self.assertEqual(record["trade_gate"],"BLOCKED")
        self.assertEqual(record["orders"],[])
    def test_prior_or_stale_blocks(self):
        record,reason=prepare("test/repo",preflight("BLOCKED"),NOW,runs(),1,500)
        self.assertIsNone(record)
        self.assertEqual(reason,"PREFLIGHT_NOT_PASSED")
        record,reason=prepare("test/repo",preflight(),
                    dt.datetime(2026,11,3,14,50,tzinfo=TZ),runs(),1,500)
        self.assertIsNone(record)
        self.assertEqual(reason,"LATEST_SAFETY_RECHECK_BLOCKED")
    def test_new_concurrent_run_blocks(self):
        active=runs()+[dict(id=2,event="workflow_dispatch",
             status="in_progress",conclusion=None,
             path=".github/workflows/p1-fresh-vendor-roster.yml",
             created_at="2026-11-03T06:23:00Z")]
        record,reason=prepare("test/repo",preflight(),NOW,active,2,500)
        self.assertIsNone(record)
        self.assertEqual(reason,"LATEST_SAFETY_RECHECK_BLOCKED")
    def test_disabled_never_reserves_or_dispatches(self):
        record,_=prepare("test/repo",preflight(),NOW,runs(),1,500)
        with patch("collector.p1_recovery_dispatch_once.api") as api,patch(
             "collector.p1_recovery_dispatch_once.subprocess.run") as run:
            status=request_once("test/repo",record,enabled=False)
        self.assertEqual(status,"DISPATCH_DISABLED")
        api.assert_not_called();run.assert_not_called()
    def test_create_only_and_duplicate_not_retried(self):
        record,_=prepare("test/repo",preflight(),NOW,runs(),1,500)
        path=record["attempt_path"]
        payload={}
        def api_func(repo,endpoint,*,method="GET",data=None):
            if method=="PUT":
                self.assertNotIn("sha",data)
                self.assertEqual(data["branch"],"research-intraday-snapshots")
                payload["content"]=data["content"]
                return {}
            return ({"path":path,"content":payload["content"]}
                    if payload else None)
        with patch("collector.p1_recovery_dispatch_once.api",
                   side_effect=api_func) as api:
            self.assertTrue(reserve_attempt("test/repo",record))
            self.assertFalse(reserve_attempt("test/repo",record))
        self.assertEqual(api.call_count,4)
    def test_race_prevents_dispatch(self):
        record,_=prepare("test/repo",preflight(),NOW,runs(),1,500)
        with patch("collector.p1_recovery_dispatch_once.api",side_effect=[
            None,RuntimeError("409"),{"path":record["attempt_path"]}]),patch(
             "collector.p1_recovery_dispatch_once.subprocess.run") as run:
            self.assertEqual(request_once("test/repo",record,enabled=True),
                             "ALREADY_RESERVED_NO_RETRY")
        run.assert_not_called()
    def test_accepted_dispatch_is_not_completed_collection(self):
        record,_=prepare("test/repo",preflight(),NOW,runs(),1,500)
        from unittest.mock import Mock
        with patch("collector.p1_recovery_dispatch_once.reserve_attempt",
                   return_value=True),patch(
             "collector.p1_recovery_dispatch_once.subprocess.run",
             return_value=Mock(returncode=0)) as run:
            status=request_once("test/repo",record,enabled=True)
        self.assertEqual(status,"DISPATCH_REQUEST_ACCEPTED_NOT_COLLECTION_VERIFIED")
        self.assertEqual(run.call_count,1)
        data=json.loads(run.call_args.kwargs["input"])
        self.assertEqual(data["inputs"],{"shards_per_run":"1",
                                         "recovery_token":"p1r-20261103-1310-500"})
    def test_failed_request_not_retried(self):
        record,_=prepare("test/repo",preflight(),NOW,runs(),1,500)
        from unittest.mock import Mock
        with patch("collector.p1_recovery_dispatch_once.reserve_attempt",
                   return_value=True),patch(
             "collector.p1_recovery_dispatch_once.subprocess.run",
             return_value=Mock(returncode=1)) as run:
            self.assertEqual(request_once("test/repo",record,enabled=True),
                             "DISPATCH_OUTCOME_UNKNOWN_DO_NOT_RETRY")
        run.assert_called_once()
if __name__=="__main__":unittest.main()
