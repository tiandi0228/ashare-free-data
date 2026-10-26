import unittest
from collector.p1_quad_pick import choose
class PickTests(unittest.TestCase):
    def plan(self):
        return {"phase":"P1_FRESH_VENDOR_SHARD_PLAN","trade_gate":"BLOCKED",
                "source_sha256":"a"*64,"shard_count":7,
                "shards":[{"index":i} for i in range(7)]}
    def test_four_missing(self):
        self.assertEqual(choose(self.plan(),start_index=3),[3,4,5,6])
    def test_wrap_and_skip_completed(self):
        prior={"source_sha256":"a"*64,"shard_count":7,"trade_gate":"BLOCKED",
               "completed":[{"index":i} for i in [0,1,2,3,4]]}
        self.assertEqual(choose(self.plan(),prior,start_index=2),[5,6])
    def test_changed_epoch_fails(self):
        with self.assertRaises(ValueError):
            choose(self.plan(),{"source_sha256":"b"*64,"shard_count":7,
                                "trade_gate":"BLOCKED","completed":[]})
if __name__=="__main__":unittest.main()
