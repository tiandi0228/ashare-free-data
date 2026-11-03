"""Dry-run recovery claim must be create-only, idempotent, no trade."""
import base64,datetime as dt,json,unittest
from unittest.mock import patch
from collector.p1_recovery_claim import claim_path,reserve

def report(state="ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW",slot="2026-11-03T13:10:00+08:00"):
    return {"state":state,"slot":slot,"requested_shards":1,
            "auto_dispatch_enabled":False,"auto_dispatched":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

class RecoveryClaimTests(unittest.TestCase):
    def test_slot_path_exact_and_unapproved_hour_rejected(self):
        self.assertEqual(claim_path(report()),
                         "recovery-claims/2026-11-03/1310.json")
        with self.assertRaisesRegex(ValueError,"approved schedule"):
            claim_path(report(slot="2026-11-03T12:10:00+08:00"))
        with self.assertRaisesRegex(ValueError,"scheduled slot"):
            claim_path(report(slot="2026-11-03T13:11:00+08:00"))

    def test_not_eligible_never_calls_remote(self):
        with patch("collector.p1_recovery_claim.api") as api:
            result=reserve("test/repo",report(state="RECOVERY_BLOCKED"),10)
        api.assert_not_called()
        self.assertEqual(result["state"],"NOT_ELIGIBLE")

    def test_invalid_trade_gate_or_dispatch_rejected(self):
        for key,val in (("trade_gate","OPEN"),("auto_dispatch_enabled",True),
                        ("auto_dispatched",True),("requested_shards",2),
                        ("orders",["BUY"])):
            q=report();q[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):
                reserve("test/repo",q,10)

    def test_marker_created_without_overwrite_and_readback(self):
        q=report();path=claim_path(q)
        def respond(repo_name,endpoint,*,method="GET",data=None):
            if method=="PUT":
                self.assertNotIn("sha",data)
                self.assertEqual(data["branch"],"research-intraday-snapshots")
                obj=json.loads(base64.b64decode(data["content"]))
                self.assertFalse(obj["auto_dispatched"])
                self.assertEqual(obj["origin_check_run_id"],10)
                self.raw=base64.b64decode(data["content"])
                return {}
            if not hasattr(self,"raw"):return None
            return {"path":path,"content":base64.b64encode(self.raw).decode()}
        with patch("collector.p1_recovery_claim.api",side_effect=respond) as api:
            result=reserve("test/repo",q,10)
        self.assertEqual(result["state"],"DRY_RUN_CLAIMED")
        self.assertEqual(api.call_count,3)
        self.assertFalse(result["auto_dispatched"])

    def test_prior_claim_no_write(self):
        p=claim_path(report())
        with patch("collector.p1_recovery_claim.api",return_value={"path":p}) as api:
            result=reserve("test/repo",report(),10)
        self.assertEqual(result["state"],"ALREADY_CLAIMED")
        api.assert_called_once()

    def test_race_has_one_winner(self):
        p=claim_path(report())
        with patch("collector.p1_recovery_claim.api",
                   side_effect=[None,RuntimeError("409 conflict"),{"path":p}]):
            result=reserve("test/repo",report(),10)
        self.assertEqual(result["state"],"ALREADY_CLAIMED")
        self.assertFalse(result["auto_dispatched"])

    def test_remote_readback_mismatch_fails(self):
        p=claim_path(report())
        with patch("collector.p1_recovery_claim.api",side_effect=[
                None,{},{"path":p,"content":base64.b64encode(b"{}").decode()}]):
            with self.assertRaisesRegex(ValueError,"readback differs"):
                reserve("test/repo",report(),10)
if __name__=="__main__":unittest.main()
