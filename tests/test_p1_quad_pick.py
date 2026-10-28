import unittest
from collector.p1_quad_pick import choose,rotating_start
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
    def test_run_rotation_avoids_permanent_failed_shard_starvation(self):
        prior={"source_sha256":"a"*64,"shard_count":7,"trade_gate":"BLOCKED",
               "completed":[{"index":0}]}
        starts=[rotating_start(7,i) for i in range(7)]
        self.assertEqual(len(set(starts)),7)
        selections=[choose(self.plan(),prior,start_index=start) for start in starts]
        self.assertTrue(any(1 not in group for group in selections))
        self.assertTrue(all(len(group)==4 and len(set(group))==4 for group in selections))

    def test_invalid_run_rotation_fails_closed(self):
        for value in (-1,True,"2"):
            with self.assertRaises(ValueError):
                rotating_start(7,value)

    def test_changed_epoch_fails(self):
        with self.assertRaises(ValueError):
            choose(self.plan(),{"source_sha256":"b"*64,"shard_count":7,
                                "trade_gate":"BLOCKED","completed":[]})
if __name__=="__main__":unittest.main()
