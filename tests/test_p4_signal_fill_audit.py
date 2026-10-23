import unittest
from collector.p4_signal_fill_audit import assess
class SignalFillTests(unittest.TestCase):
    def sample(self):
        return dict(signal_id="x",trade_gate="BLOCKED",orders=[],source_observed_at="2026-10-20T07:00:00+00:00",signal_completed_at="2026-10-20T07:01:00+00:00",execution_status="UNFILLED",fill=None)
    def test_unfilled_excluded(self):
        r=assess([self.sample()])
        self.assertEqual(r["unfilled_signal_count"],1)
        self.assertFalse(r["records"][0]["return_included"])
    def test_no_future_data(self):
        with self.assertRaises(ValueError):assess([{**self.sample(),"source_observed_at":"2026-10-20T08:00:00+00:00"}])
    def test_filled_requires_later_receipt(self):
        s={**self.sample(),"execution_status":"FILLED","fill":{"filled_at":"2026-10-20T07:02:00+00:00","independent_execution_receipt_sha256":"a"*64}}
        r=assess([s])
        self.assertEqual(r["fill_evidence_count"],1)
        self.assertFalse(r["returns_computed"])
    def test_no_implicit_fill(self):
        with self.assertRaises(ValueError):assess([{**self.sample(),"execution_status":"FILLED"}])
if __name__=="__main__":unittest.main()
