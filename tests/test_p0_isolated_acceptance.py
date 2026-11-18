import copy
import unittest
from collector.p0_isolated_acceptance import MODULES,evaluate

def rows():
    return [{"module":m,"returncode":0,"ran_tests":True,"reported_ok":True} for m in MODULES]

class P0AcceptanceTests(unittest.TestCase):
    def test_pass_still_not_production(self):
        r=evaluate(rows())
        self.assertEqual(r["selected_offline_modules_passed"],4)
        self.assertEqual(r["historical_development_completion_claim_pct"],100)
        self.assertIsNone(r["current_complete_P0_phase_acceptance_pct"])
        self.assertFalse(r["live_quote_freshness_verified"])
        self.assertFalse(r["production_ready"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_failed_module_does_not_pass(self):
        a=rows();a[2]["returncode"]=1
        r=evaluate(a)
        self.assertEqual(r["status"],"OFFLINE_TEST_FAILURE")
        self.assertEqual(r["selected_offline_modules_passed"],3)
        self.assertFalse(r["historical_claim_reverified_as_phase_completion"])
    def test_missing_module_rejected(self):
        with self.assertRaises(ValueError):evaluate(rows()[:3])
    def test_forged_module_rejected(self):
        a=rows();a[1]["module"]="tests.fake"
        with self.assertRaises(ValueError):evaluate(a)
    def test_no_tests_executed_is_not_pass(self):
        a=rows();a[0]["ran_tests"]=False
        self.assertEqual(evaluate(a)["status"],"OFFLINE_TEST_FAILURE")
    def test_no_ok_marker_is_not_pass(self):
        a=rows();a[0]["reported_ok"]=False
        self.assertEqual(evaluate(a)["status"],"OFFLINE_TEST_FAILURE")
    def test_truthy_numeric_marker_rejected(self):
        a=rows();a[0]["reported_ok"]=1
        with self.assertRaises(ValueError):evaluate(a)
if __name__=="__main__":
    unittest.main()
