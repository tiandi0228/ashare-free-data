import unittest
from collector.p4_flat_bar_risk import flags
class FlatTests(unittest.TestCase):
    def row(self,day,p,status="1"):
        return dict(code="sh.600001",date=day,open=p,high=p,low=p,close=p,volume="100",tradestatus=status)
    def test_up(self):
        r=flags([self.row("2026-11-23","10"),self.row("2026-11-24","11")])[0]
        self.assertEqual(r["hypotheses"],[dict(side="UP",assumed_band_pct="10.00")]);self.assertFalse(r["fill_verified"])
    def test_down(self):
        r=flags([self.row("2026-11-23","10"),self.row("2026-11-24","9.5")])[0]
        self.assertEqual(r["hypotheses"][0]["side"],"DOWN")
    def test_not_adjacent(self):
        self.assertEqual(flags([self.row("2026-11-23","10"),self.row("2026-11-25","11")]),[])
    def test_halt(self):
        self.assertEqual(flags([self.row("2026-11-23","10","0"),self.row("2026-11-24","11")]),[])
    def test_other(self):
        self.assertEqual(flags([self.row("2026-11-23","10"),self.row("2026-11-24","10.1")])[0]["hypotheses"],[])
