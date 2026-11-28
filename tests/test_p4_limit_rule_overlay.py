import unittest
from collector.p4_limit_rule_overlay import classify
class RuleTests(unittest.TestCase):
    def test_boundary(self):
        self.assertTrue(classify("2026-07-03",["5.00"]).startswith("GENERAL_RULE_COMPATIBLE"))
        self.assertTrue(classify("2026-07-06",["5.00"]).startswith("GENERAL_RULE_MISMATCH"))
    def test_ten(self):
        self.assertTrue(classify("2026-11-25",["10.00"]).startswith("GENERAL_RULE_COMPATIBLE"))
    def test_unknown(self):
        with self.assertRaises(ValueError):classify("2026-11-25",["20.00"])
