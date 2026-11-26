import unittest
from collector.p2_residual_risk import classify
class ResidualTests(unittest.TestCase):
    def test_halt_not_delisted(self):
        self.assertEqual(classify("sz.002717",{"missing_expected_sessions":[]},[{"tradestatus":"0"}]*26,True),"HALTED_PENDING_DELIST_DECISION")
    def test_delist_tail(self):
        self.assertEqual(classify("sz.002731",{"missing_expected_sessions":["2026-11-13"]},[{"date":"2026-11-12"}],True),"DELISTED_RETROSPECTIVE")
    def test_unverified(self):
        self.assertEqual(classify("sz.002731",{},[],False),"UNVERIFIED_NOTICE")
