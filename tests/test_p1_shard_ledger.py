import unittest
from collector.p1_shard_ledger import reconcile

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.plan={"phase":"P1_FRESH_VENDOR_SHARD_PLAN","source_sha256":"a"*64,
                   "shard_count":2,"shards":[{"index":0,"sha256":"b"*64,"count":8},
                                              {"index":1,"sha256":"c"*64,"count":3}]}
    def receipt(self,index):
        s=self.plan["shards"][index]
        return {"manifest_sha256":s["sha256"],"issuer_count":s["count"],
                "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                "paid_api_calls":0,"query_attempts":s["count"],
                "results":[{"status":"OBSERVED_UNVERIFIED","sha256":"d"*64} for _ in range(s["count"])]}
    def test_progress_resume_and_next(self):
        a=reconcile(self.plan,[(0,self.receipt(0))])
        self.assertEqual((a["completed_issuers"],a["next_shard"]),(8,1))
        b=reconcile(self.plan,[(1,self.receipt(1))],a)
        self.assertEqual((b["completed_issuers"],b["next_shard"]),(11,None))
        self.assertEqual(b["trade_gate"],"BLOCKED")
    def test_changed_roster_rejected(self):
        a=reconcile(self.plan,[(0,self.receipt(0))])
        changed={**self.plan,"source_sha256":"z"*64}
        with self.assertRaises(ValueError):reconcile(changed,[],a)
    def test_duplicate_prior_receipt_rejected(self):
        prior=reconcile(self.plan,[(0,self.receipt(0))])
        prior["completed"].append(dict(prior["completed"][0]))
        with self.assertRaises(ValueError):
            reconcile(self.plan,[],prior)
    def test_missing_prior_receipt_sha_rejected(self):
        prior=reconcile(self.plan,[(0,self.receipt(0))])
        del prior["completed"][0]["receipt_sha256"]
        with self.assertRaises(ValueError):
            reconcile(self.plan,[],prior)
    def test_bad_receipt_not_counted(self):
        r=self.receipt(0);r["results"][0]["status"]="ERROR"
        a=reconcile(self.plan,[(0,r)])
        self.assertEqual(a["completed_issuers"],0)
        self.assertEqual(a["failed_in_this_reconciliation"],[0])
if __name__=="__main__":unittest.main()
