import unittest
from decimal import Decimal as D
from collector.p2_short_risk_proxy import budget,observe,feasibility,pnl
from unittest.mock import patch
class RiskTests(unittest.TestCase):
    def setUp(self):
        self.days=["2026-11-16","2026-11-17","2026-11-18","2026-11-19","2026-11-20","2026-11-23"]
        self.bars={d:dict(open="10",high="10.1",low="9.9",close="10",volume="100",tradestatus="1") for d in self.days}
    def test_budget(self):
        self.assertTrue(feasibility()["impossible_under_frozen_parameters"])
        self.assertLess(D(feasibility()["net_reward_risk_upper_bound"]),2)
        for p in ("0.01","1","10","39","79","80","100"):
            self.assertIsNone(budget(D(p)))
        self.assertEqual(observe(self.days[0],self.bars,self.days)["status"],"RISK_BUDGET_REJECTED")
    def test_invalid_price(self):
        with self.assertRaises(ValueError):budget(D("0"))
    def hypothetical_budget(self):
        # Test the exit state machine separately with a synthetic feasible plan.
        # This is never used in production or historical evaluation.
        q=700;b=D("10.01");s=D("9.8");t=D("10.6")
        l=-pnl(b,s*D(".999"),q);r=pnl(b,t*D(".999"),q)
        self.assertLessEqual(l,D("240"));self.assertGreaterEqual(r,2*l)
        return patch("collector.p2_short_risk_proxy.budget",return_value=(q,b,s,t,l,r))
    def test_t1(self):
        self.bars[self.days[1]]["low"]="9"
        with self.hypothetical_budget():
            self.assertEqual(observe(self.days[0],self.bars,self.days)["exit_reason"],"FRIDAY_CLOSE")
    def test_dual(self):
        self.bars[self.days[2]].update(low="9",high="11")
        with self.hypothetical_budget():
            self.assertEqual(observe(self.days[0],self.bars,self.days)["status"],"AMBIGUOUS_DUAL_TOUCH")
    def test_gap(self):
        self.bars[self.days[2]].update(open="8",low="8",high="8.1",close="8")
        with self.hypothetical_budget():
            r=observe(self.days[0],self.bars,self.days)
        self.assertEqual(r["exit_reason"],"GAP_BELOW_STOP");self.assertTrue(r["loss_budget_breached"])
    def test_friday_entry(self):
        self.assertEqual(observe(self.days[3],self.bars,self.days)["status"],"FRIDAY_ENTRY_BLOCKED")
    def test_missing_exit(self):
        del self.bars[self.days[2]]
        with self.hypothetical_budget():
            self.assertEqual(observe(self.days[0],self.bars,self.days)["status"],"EXIT_WINDOW_UNAVAILABLE")
