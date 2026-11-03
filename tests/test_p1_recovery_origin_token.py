"""Research recovery token must match the immutable slot, but is not auth."""
import unittest
from collector.p1_recovery_origin_token import token_for_attempt,target_receipt
def attempt():
    return {"phase":"P1_SINGLE_SHARD_DISPATCH_ATTEMPT",
            "state":"DISPATCH_ATTEMPT_RESERVED","requested_shards":1,
            "origin_check_run_id":500,
            "slot":"2026-11-03T13:10:00+08:00",
            "attempt_path":"recovery-dispatch-attempts/2026-11-03/1310.json",
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
class OriginTokenTests(unittest.TestCase):
    def test_exact_token_from_attempt(self):
        self.assertEqual(token_for_attempt(attempt()),"p1r-20261103-1310-500")
    def test_invalid_attempt_rejected(self):
        for field,value in [("origin_check_run_id",0),("requested_shards",2),
                            ("attempt_path","recovery-dispatch-attempts/2026-11-03/1510.json"),
                            ("trade_gate","OPEN"),("slot","2026-11-03T12:10:00+08:00")]:
            with self.subTest(field=field):
                x=attempt();x[field]=value
                with self.assertRaises(ValueError):token_for_attempt(x)
    def test_target_receipt_observes_token_without_claiming_completion(self):
        r=target_receipt(token=token_for_attempt(attempt()),event_name="workflow_dispatch",
                         run_id=601,shards="1",ref="refs/heads/main")
        self.assertEqual(r["state"],"RECOVERY_TOKEN_OBSERVED_UNVERIFIED")
        self.assertEqual(r["recovery_token"],"p1r-20261103-1310-500")
        self.assertEqual(r["origin_check_run_id"],500)
        self.assertFalse(r["historical_collection_verified"])
        self.assertFalse(r["causal_dispatch_link_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_regular_scheduled_run_has_no_token(self):
        r=target_receipt(token="",event_name="schedule",run_id=601,
                         shards="2",ref="refs/heads/main")
        self.assertEqual(r["state"],"NORMAL_OR_UNTAGGED_COLLECTION")
        self.assertIsNone(r["recovery_token"])
    def test_token_rejected_on_push_or_two_shards_or_bad_ref(self):
        for event,shards,ref in [("push","1","refs/heads/main"),
                                 ("workflow_dispatch","2","refs/heads/main"),
                                 ("workflow_dispatch","1","refs/heads/feature")]:
            with self.subTest(event=event,shards=shards,ref=ref):
                with self.assertRaises(ValueError):
                    target_receipt(token="p1r-20261103-1310-500",event_name=event,
                                   run_id=601,shards=shards,ref=ref)
    def test_forged_or_malformed_token_rejected(self):
        for token in ("p1r-20261103-1311-500","p1r-20261103-1210-500",
                      "p1r-20261103-1310-0","p1r-20261340-1310-500",
                      "p1r-20261103-1310-500\nINJECT"):
            with self.subTest(token=token),self.assertRaises(ValueError):
                target_receipt(token=token,event_name="workflow_dispatch",
                               run_id=601,shards="1",ref="refs/heads/main")
if __name__=="__main__":unittest.main()
