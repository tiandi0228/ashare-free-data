"""No dispatch on dry-run markers, invalid proof or stale eligibility."""
import base64,datetime as dt,json,os,unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from collector.p1_recovery_dispatch_preflight import inspect,PHASE
from collector.p1_recovery_claim import PHASE as CLAIM_PHASE

TZ=ZoneInfo("Asia/Shanghai")
NOW=dt.datetime(2026,11,3,14,25,tzinfo=TZ)
PATH="recovery-claims/2026-11-03/1310.json"
def claim(run_id=77):
    return {"phase":CLAIM_PHASE,"slot":"2026-11-03T13:10:00+08:00",
            "origin_check_run_id":run_id,
            "mode":"DRY_RUN_NO_DISPATCH","auto_dispatched":False,
            "historical_collection_executed":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def remote(record=None):
    return {"path":PATH,"content":base64.b64encode(
        json.dumps(claim() if record is None else record).encode()).decode()}
def runs():
    t=dt.datetime(2026,11,3,11,12,tzinfo=TZ)
    return [{"id":40,"event":"schedule","status":"completed",
             "conclusion":"success",
             "created_at":t.isoformat(),
             "path":".github/workflows/p1-fresh-vendor-roster.yml"}]
class PreflightTests(unittest.TestCase):
    def test_fresh_claim_preflight_never_dispatches(self):
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"77"}),patch(
            "collector.p1_recovery_dispatch_preflight.api",return_value=remote()) as api:
            result=inspect("test/repo",{"state":"DRY_RUN_CLAIMED","claim_path":PATH},
                           NOW,runs(),1)
        self.assertEqual(result["state"],"PREFLIGHT_PASS_DISPATCH_NOT_ENABLED")
        self.assertFalse(result["dispatch_authorized"])
        self.assertFalse(result["dispatch_attempted"])
        self.assertFalse(result["historical_collection_executed"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        api.assert_called_once()
    def test_prior_marker_not_a_new_execution(self):
        with patch("collector.p1_recovery_dispatch_preflight.api") as api:
            r=inspect("test/repo",{"state":"ALREADY_CLAIMED",
                     "claim_path":PATH},NOW,runs(),1)
        self.assertEqual(r["reason"],"NO_NEW_DRY_RUN_CLAIM")
        api.assert_not_called()
    def test_claim_from_other_run_blocked(self):
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"99"}),patch(
            "collector.p1_recovery_dispatch_preflight.api",return_value=remote()):
            r=inspect("test/repo",{"state":"DRY_RUN_CLAIMED",
                      "claim_path":PATH},NOW,runs(),1)
        self.assertEqual(r["reason"],"CLAIM_PROVENANCE_MISMATCH")
    def test_stale_guard_blocked(self):
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"77"}),patch(
            "collector.p1_recovery_dispatch_preflight.api",return_value=remote()):
            r=inspect("test/repo",{"state":"DRY_RUN_CLAIMED",
                      "claim_path":PATH},
                      dt.datetime(2026,11,3,14,50,tzinfo=TZ),runs(),1)
        self.assertEqual(r["reason"],"FRESH_P1_GUARD_BLOCKED")
    def test_corrupt_remote_claim_blocked(self):
        invalid=claim();invalid["auto_dispatched"]=True
        with patch.dict(os.environ,{"GITHUB_RUN_ID":"77"}),patch(
            "collector.p1_recovery_dispatch_preflight.api",
            return_value=remote(invalid)):
            r=inspect("test/repo",{"state":"DRY_RUN_CLAIMED",
                      "claim_path":PATH},NOW,runs(),1)
        self.assertEqual(r["reason"],"CLAIM_PROVENANCE_MISMATCH")
if __name__=="__main__":unittest.main()
