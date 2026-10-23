import unittest
from collector.p1_checkpoint import merge,validate,epoch_path

class CheckpointTests(unittest.TestCase):
    def ledger(self,n):
        return {"phase":"P1_ROSTER_SHARD_LEDGER","trade_gate":"BLOCKED",
                "historical_PIT_verified":False,"orders":[],"executable_candidates":[],
                "source_sha256":"a"*64,"shard_count":2,
                "completed":[{"index":i,"issuer_count":8,"manifest_sha256":"b"*64,"receipt_sha256":"c"*64} for i in range(n)],
                "completed_shards":n,"completed_issuers":n*8}
    def test_epoch_checkpoint_is_content_addressed(self):
        self.assertEqual(epoch_path("a"*64),"evidence/checkpoints/"+"a"*64+".json")
        with self.assertRaises(ValueError):epoch_path("../invalid")
    def test_higher_progress_is_preserved(self):
        self.assertEqual(merge(self.ledger(0),self.ledger(1))["completed_issuers"],8)
    def test_new_progress_wins(self):
        self.assertEqual(merge(self.ledger(2),self.ledger(1))["completed_issuers"],16)
    def test_other_roster_is_rejected(self):
        other=self.ledger(1);other["source_sha256"]="z"*64
        with self.assertRaises(ValueError):merge(self.ledger(2),other)
    def test_equal_count_replacement_rejected(self):
        newer=self.ledger(1)
        older=self.ledger(1)
        newer["completed"][0]["receipt_sha256"]="d"*64
        with self.assertRaises(ValueError):merge(newer,older)
    def test_added_shard_preserves_old_evidence(self):
        self.assertEqual(merge(self.ledger(2),self.ledger(1))["completed_issuers"],16)
    def test_orders_rejected(self):
        candidate=self.ledger(0);candidate["orders"]=[{"buy":"SH"}]
        with self.assertRaises(ValueError):validate(candidate)
    def test_inconsistent_totals_rejected(self):
        candidate=self.ledger(1);candidate["completed_issuers"]=500
        with self.assertRaises(ValueError):validate(candidate)
if __name__=="__main__":unittest.main()
