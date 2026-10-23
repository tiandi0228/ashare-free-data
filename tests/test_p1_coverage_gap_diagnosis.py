import unittest
from collector.p1_coverage_gap_diagnosis import diagnose

class DiagnoseTests(unittest.TestCase):
    def setup_data(self):
        plan={"source_sha256":"a"*64,"shard_count":3,"shards":[{"index":i,"count":8,"sha256":str(i)*64} for i in range(3)]}
        ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED","completed":[{"index":0}],
                "completed_shards":1,"completed_issuers":8,"pending_shards":[1,2]}
        archive={"trade_gate":"BLOCKED","archived_issuers":8,"archive_gap_issuers":0,"archive_repair_queue":[]}
        return plan,ledger,archive
    def test_next_pending_and_fail_closed(self):
        a,b,c=self.setup_data()
        r=diagnose(a,b,c)
        self.assertEqual(r["next_shard_index"],1)
        self.assertEqual(r["pending_issuers"],16)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        b["source_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"mixed roster"):diagnose(a,b,c)
    def test_archive_repair_precedes_new_collection(self):
        a,b,c=self.setup_data()
        c.update(archived_issuers=0,archive_gap_issuers=8,archive_repair_queue=[0])
        r=diagnose(a,b,c)
        self.assertEqual(r["next_action"],"REPAIR_VERIFIED_ARCHIVE")
        self.assertEqual(r["next_shard_index"],0)
    def test_inconsistent_counts_fail(self):
        a,b,c=self.setup_data()
        b["completed_issuers"]=16
        with self.assertRaisesRegex(ValueError,"issuer count"):diagnose(a,b,c)
if __name__=="__main__":unittest.main()
