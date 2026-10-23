import unittest
from collector.p234_historical_readiness import assess,REQUIREMENTS

class HistoricalReadinessTests(unittest.TestCase):
    def test_unverified_fails_closed(self):
        result=assess({"trade_gate":"BLOCKED","orders":[]})
        self.assertEqual(result["missing_requirements"],list(REQUIREMENTS))
        self.assertFalse(result["permission_to_trade"])
    def test_vendor_provenance_not_official_pit(self):
        source={"trade_gate":"BLOCKED","orders":[]}
        source.update({key:{"verified":True,"scope":"CURRENT_VENDOR_ONLY","audit_id":"x","original_source_sha256":"a"*64} for key in REQUIREMENTS})
        self.assertFalse(assess(source)["requirements_met"])
    def test_even_complete_metadata_never_opens_orders(self):
        source={"trade_gate":"BLOCKED","orders":[]}
        source.update({key:{"verified":True,"scope":"HISTORICAL_POINT_IN_TIME","audit_id":"x","original_source_sha256":"a"*64} for key in REQUIREMENTS})
        result=assess(source)
        self.assertTrue(result["requirements_met"])
        self.assertFalse(result["historical_strategy_validated"])
        self.assertFalse(result["permission_to_trade"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_orders_in_input_fail(self):
        with self.assertRaises(ValueError):assess({"trade_gate":"BLOCKED","orders":[{"buy":1}]})
if __name__=="__main__":unittest.main()
