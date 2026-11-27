import unittest
from collector.p3_complete_original_ledger import merge
class CompleteTests(unittest.TestCase):
    def test_unsafe(self):
        with self.assertRaises(ValueError):merge(dict(asof="2026-11-25",trade_gate="OPEN"),{}, {})
    def test_wrong_scope(self):
        x=dict(asof="2026-11-25",trade_gate="BLOCKED",orders=[],executable_candidates=[],official_certified=0,historical_PIT_verified=False,records=[],original_issuers_verified=15)
        with self.assertRaises(ValueError):merge(x,x,x)
