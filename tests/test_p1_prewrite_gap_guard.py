"""P1 prewrite gap preflight adversarial tests: no GitHub writes, no vendors."""
import copy
import unittest
from collector.p1_prewrite_gap_guard import check

SHA="a"*64

def fixtures():
    plan={"phase":"P1_FRESH_VENDOR_SHARD_PLAN","trade_gate":"BLOCKED",
          "historical_PIT_verified":False,"orders":[],"executable_candidates":[],
          "source_sha256":SHA,"shard_count":7,"issuer_count":7,
          "shards":[{"index":i,"name":f"shard_{i:04d}.txt","count":1,
                     "sha256":f"{i+1:064x}"} for i in range(7)]}
    ledger={"phase":"P1_ROSTER_SHARD_LEDGER","trade_gate":"BLOCKED",
            "historical_PIT_verified":False,"full_market_bars_certified":False,
            "orders":[],"executable_candidates":[],"source_sha256":SHA,
            "shard_count":7,"completed_shards":5,"completed_issuers":5,
            "completed":[{"index":i,"issuer_count":1,
                          "manifest_sha256":f"{i+1:064x}",
                          "receipt_sha256":f"{i+100:064x}"} for i in range(5)],
            "pending_shards":[5,6],"next_shard":5,"failed_in_this_reconciliation":[]}
    archive={"source_sha256":SHA,"trade_gate":"BLOCKED","archived_shards":list(range(5))}
    return plan,ledger,archive

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.plan,self.ledger,self.archive=fixtures()
    def inspect(self,selected,fresh=None,archive=None,prior=None,plan=None):
        return check(plan if plan is not None else self.plan,selected,
                     prior if prior is not None else self.ledger,
                     fresh if fresh is not None else self.ledger,
                     archive if archive is not None else self.archive)
    def test_one_missing(self):
        r=self.inspect([5])
        self.assertEqual(r["selected_missing_shards"],[5])
        self.assertFalse(r["permission_to_write_or_trade"])
        self.assertTrue(r["requires_second_remote_head_check_before_write"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_two_missing(self):
        self.assertEqual(self.inspect([5,6])["selected_missing_shards"],[5,6])
    def test_existing_denied(self):
        with self.assertRaises(ValueError):self.inspect([4])
    def test_invalid_or_duplicate_selection(self):
        for selected in ([5,5],[3,5,6],[],[7],[True],["5"]):
            with self.subTest(selected=selected),self.assertRaises(ValueError):
                self.inspect(selected)
    def test_changed_checkpoint_denied(self):
        newer=copy.deepcopy(self.ledger)
        newer["completed"].append({"index":6,"issuer_count":1,
          "manifest_sha256":f"{7:064x}","receipt_sha256":f"{106:064x}"})
        newer["completed_shards"]=6;newer["completed_issuers"]=6
        newer["pending_shards"]=[5]
        with self.assertRaisesRegex(ValueError,"changed after selection"):
            self.inspect([5],fresh=newer)
    def test_extra_archived_denied(self):
        a=copy.deepcopy(self.archive);a["archived_shards"].append(5)
        with self.assertRaises(ValueError):self.inspect([5],archive=a)
    def test_missing_archived_denied(self):
        a=copy.deepcopy(self.archive);a["archived_shards"].remove(3)
        with self.assertRaises(ValueError):self.inspect([5],archive=a)
    def test_duplicate_archive_denied(self):
        a=copy.deepcopy(self.archive);a["archived_shards"].append(4)
        with self.assertRaises(ValueError):self.inspect([5],archive=a)
    def test_different_epoch_denied(self):
        newer=copy.deepcopy(self.ledger);newer["source_sha256"]="b"*64
        with self.assertRaises(ValueError):self.inspect([5],fresh=newer)
    def test_modified_plan_denied(self):
        p=copy.deepcopy(self.plan);p["shards"][1]["sha256"]="f"*64
        with self.assertRaises(ValueError):self.inspect([5],plan=p)
    def test_open_gate_denied(self):
        a=copy.deepcopy(self.archive);a["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):self.inspect([5],archive=a)
    def test_corrupt_completed_count_denied(self):
        prior=copy.deepcopy(self.ledger);prior["completed_shards"]=6
        with self.assertRaises(ValueError):self.inspect([5],prior=prior)

if __name__=="__main__":
    unittest.main()
