"""Reject nonfinite market prices and nonboolean authentication assertions."""
import unittest
from decimal import InvalidOperation
from collector.p4_calendar_limit_gate import check_execution
from collector.p4_unified_execution_preflight import assess
from tests.test_p4_calendar_limit_gate import CalendarGateTests
from tests.test_p4_unified_execution_preflight import BASE

class FailClosedLimitTests(unittest.TestCase):
    def setUp(self):
        self.params=CalendarGateTests().base()

    def test_nonfinite_values_never_pass_bar_gate(self):
        for field in ("security_limit_up","security_limit_down","observed_low",
                      "observed_high","order_limit_price"):
            for value in ("NaN","Infinity","-Infinity","sNaN"):
                with self.subTest(field=field,value=value),self.assertRaises((ValueError,InvalidOperation)):
                    check_execution(**{**self.params,field:value})

    def test_invalid_orderbook_assertions_are_not_truthy(self):
        for value in (1,0,"true","false",None,[],{}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                check_execution(**{**self.params,"orderbook_fill_evidence":value})

    def test_security_limit_auth_requires_real_bool(self):
        for value in (1,0,"true","false",None,[],{}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                assess(**{**BASE,"security_limit_authenticated":value})

    def test_unified_does_not_admit_nonfinite_prices(self):
        for field in ("security_limit_up","security_limit_down","observed_low",
                      "observed_high","order_limit_price"):
            with self.subTest(field=field),self.assertRaises((ValueError,InvalidOperation)):
                assess(**{**BASE,field:"NaN"})

    def test_missing_authentication_still_blocks_without_fill(self):
        result=assess(**{**BASE,"security_limit_authenticated":False})
        self.assertIn("SECURITY_PRICE_LIMIT_UNAUTHENTICATED",result["blocking_reasons"])
        self.assertFalse(result["candidate_for_independent_receipt_replay"])
        self.assertFalse(result["fill_certified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_valid_quote_only_reaches_independent_replay(self):
        result=assess(**BASE)
        self.assertTrue(result["candidate_for_independent_receipt_replay"])
        self.assertFalse(result["fill_certified"])
        self.assertEqual(result["executable_candidates"],[])
        self.assertEqual(result["trade_gate"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
