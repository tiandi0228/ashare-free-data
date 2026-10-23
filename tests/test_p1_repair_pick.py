import unittest
from collector.p1_repair_pick import select_repair
class RepairPickTests(unittest.TestCase):
    def setUp(self):
        self.ledger={"trade_gate":"BLOCKED","completed":[{"index":2},{"index":0}]}
    def test_select_oldest(self):
        self.assertEqual(select_repair({"trade_gate":"BLOCKED","archive_repair_queue":[0,2]},self.ledger),0)
    def test_empty(self):
        self.assertIsNone(select_repair({"trade_gate":"BLOCKED","archive_repair_queue":[]},self.ledger))
    def test_unknown_shard(self):
        with self.assertRaises(ValueError):
            select_repair({"trade_gate":"BLOCKED","archive_repair_queue":[1]},self.ledger)
    def test_untrusted_order(self):
        with self.assertRaises(ValueError):
            select_repair({"trade_gate":"BLOCKED","archive_repair_queue":[2,0]},self.ledger)
if __name__=="__main__":unittest.main()
