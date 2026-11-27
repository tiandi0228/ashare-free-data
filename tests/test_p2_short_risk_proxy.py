import unittest
from decimal import Decimal as D
from collector.p2_short_risk_proxy import budget,observe
class RiskTests(unittest.TestCase):
    def setUp(self):
        self.days=["2026-11-16","2026-11-17","2026-11-18","2026-11-19","2026-11-20","2026-11-23"]
        self.bars={d:dict(open="10",high="10.1",low="9.9",close="10",volume="100",tradestatus="1") for d in self.days}
    def test_budget(self):
        q,b,s,t,l,r=budget(D("10"))
        self.assertLessEqual(l,D("240"));self.assertGreaterEqual(r,2*l);self.assertEqual(q%100,0)
    def test_t1(self):
        self.bars[self.days[1]]["low"]="9"
        self.assertEqual(observe(self.days[0],self.bars,self.days)["exit_reason"],"FRIDAY_CLOSE")
    def test_dual(self):
        self.bars[self.days[2]].update(low="9",high="11")
        self.assertEqual(observe(self.days[0],self.bars,self.days)["status"],"AMBIGUOUS_DUAL_TOUCH")
    def test_gap(self):
        self.bars[self.days[2]].update(open="8",low="8",high="8.1",close="8")
        r=observe(self.days[0],self.bars,self.days)
        self.assertEqual(r["exit_reason"],"GAP_BELOW_STOP");self.assertTrue(r["loss_budget_breached"])
    def test_friday_entry(self):
        self.assertEqual(observe(self.days[3],self.bars,self.days)["status"],"FRIDAY_ENTRY_BLOCKED")
    def test_missing_exit(self):
        del self.bars[self.days[2]]
        self.assertEqual(observe(self.days[0],self.bars,self.days)["status"],"EXIT_WINDOW_UNAVAILABLE")
