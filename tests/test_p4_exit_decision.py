import unittest
from collector.p4_exit_decision import exit_assessment

class ExitGateTests(unittest.TestCase):
    def params(self):
        return dict(entry_day="2026-10-19",observation_day="2026-10-20",trading_sessions_elapsed=1,low=9.9,high=10.4,stop=9.7,take_profit=10.6)
    def test_no_trigger(self):
        self.assertEqual(exit_assessment(**self.params())["outcome"],"HOLD_RESEARCH_ONLY")
    def test_ambiguous_conservative(self):
        p={**self.params(),"low":9.5,"high":10.8,"tradable":True,"fill_proven":True}
        x=exit_assessment(**p)
        self.assertTrue(x["conservative_stop_precedence"])
        self.assertFalse(x["recorded_fill"])
        self.assertEqual(x["orders"],[])
    def test_no_fill_on_suspend(self):
        p={**self.params(),"low":9.5,"tradable":False,"fill_proven":False}
        self.assertEqual(exit_assessment(**p)["outcome"],"NO_VERIFIED_EXECUTION_SUSPENDED_OR_LIMITED")
    def test_dplus3_no_implied_fill(self):
        p={**self.params(),"trading_sessions_elapsed":3,"tradable":True}
        x=exit_assessment(**p)
        self.assertIn("D_PLUS_3",x["reasons"])
        self.assertFalse(x["recorded_fill"])
    def test_friday_exit(self):
        p={**self.params(),"observation_day":"2026-10-23"}
        self.assertIn("FRIDAY_EXIT",exit_assessment(**p)["reasons"])
    def test_tplus1(self):
        with self.assertRaises(ValueError):exit_assessment(**{**self.params(),"observation_day":"2026-10-19"})
if __name__=="__main__":unittest.main()
