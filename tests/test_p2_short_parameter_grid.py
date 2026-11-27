import unittest
from decimal import Decimal as D
from collector.p2_short_risk_proxy import budget,feasibility
from collector.p2_short_parameter_grid import GRID
class GridTests(unittest.TestCase):
    def test_baseline_unchanged(self):
        self.assertEqual(feasibility(),feasibility(D(".02"),D(".05")))
        self.assertIsNone(budget(D("10")))
    def test_hypothetical_feasible(self):
        for name,s,t in GRID[1:]:
            self.assertFalse(feasibility(D(s),D(t))["impossible_under_frozen_parameters"])
            q,b,stop,target,loss,reward=budget(D("10"),D(s),D(t))
            self.assertGreaterEqual(reward,2*loss)
            self.assertLessEqual(loss,D("240"))
            self.assertEqual(q%100,0)
