import unittest
from collector.p3_residual_notice_bridge import classify
class BridgeTests(unittest.TestCase):
    def test_pending(self):
        self.assertEqual(classify(dict(issuer="sz.002717",vendor_nontradable_days=list(range(26)),missing_expected_sessions=[],trailing_tradable_observations=0)),"HALTED_PENDING_DELIST_DECISION")
    def test_wrong_interval(self):
        with self.assertRaises(ValueError):classify(dict(issuer="sz.002717",vendor_nontradable_days=[],missing_expected_sessions=[],trailing_tradable_observations=0))
    def test_delisted(self):
        t=dict(issuer="sz.002731",missing_expected_sessions=["2026-11-13","2026-11-16","2026-11-17","2026-11-18","2026-11-19","2026-11-20","2026-11-23","2026-11-24","2026-11-25"],trailing_tradable_observations=15)
        self.assertEqual(classify(t),"DELISTED_RETROSPECTIVE")
        t["missing_expected_sessions"].pop()
        with self.assertRaises(ValueError):classify(t)
