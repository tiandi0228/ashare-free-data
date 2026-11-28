import unittest
from collector.p3_risk_timeline import reconcile
class TimelineTests(unittest.TestCase):
    def test_matched(self):
        self.assertEqual(reconcile("2026-11-23","2026-11-24",["2026-11-23"],["2026-11-24"],["2026-11-23","2026-11-24"],"2026-11-25"),"RETROSPECTIVE_INTERVAL_MATCH")
    def test_future(self):
        self.assertEqual(reconcile("2026-11-25","2026-11-26",["2026-11-25"],[],["2026-11-25"],"2026-11-25"),"ANNOUNCED_RESUME_AFTER_CUTOFF")
    def test_missing_resume(self):
        with self.assertRaises(ValueError):reconcile("2026-11-23","2026-11-24",["2026-11-23"],[],["2026-11-23","2026-11-24"],"2026-11-25")
    def test_gap(self):
        with self.assertRaises(ValueError):reconcile("2026-11-23","2026-11-25",["2026-11-23"],["2026-11-25"],["2026-11-23","2026-11-24","2026-11-25"],"2026-11-25")
