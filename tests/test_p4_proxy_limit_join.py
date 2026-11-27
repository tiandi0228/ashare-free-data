import unittest
from collector.p4_proxy_limit_join import classify,reconcile
class JoinTests(unittest.TestCase):
    def setUp(self):
        self.r=dict(code="sh.600001",signal_day="2026-11-20",entry_day="2026-11-23",exit_day="2026-11-24",status="PRICED_EXIT_PROXY",execution_verified=False)
        self.sig={("sh.600001","2026-11-20")}
        self.flags={("sh.600001","2026-11-23"):{"UP"},("sh.600001","2026-11-24"):{"DOWN"}}
    def test_directional(self):
        x=classify(self.r,self.flags);self.assertTrue(x["entry_up_hypothesis"]);self.assertTrue(x["exit_down_hypothesis"]);self.assertFalse(x["execution_verified"])
        y=reconcile([self.r],self.flags,{"sh.600001"},self.sig)
        self.assertEqual(y["counts"]["directional_risk_observations"],1)
    def test_other_direction(self):
        x=classify(self.r,{("sh.600001","2026-11-23"):{"DOWN"}})
        self.assertEqual(x["execution_status"],"NO_DIRECTIONAL_FLAG_NOT_FILL_PROOF")
        self.assertEqual(x["any_flagged_window_days"],["2026-11-23"])
    def test_duplicate(self):
        with self.assertRaises(ValueError):reconcile([self.r,self.r],self.flags,{"sh.600001"},self.sig)
    def test_missing(self):
        with self.assertRaises(ValueError):reconcile([],self.flags,{"sh.600001"},self.sig)
    def test_same_day(self):
        with self.assertRaises(ValueError):classify(dict(self.r,exit_day=self.r["entry_day"]),self.flags)
    def test_unpriced_retained(self):
        x=reconcile([dict(self.r,status="RIGHT_CENSORED")],self.flags,{"sh.600001"},self.sig)
        self.assertEqual(x["counts"]["not_priced"],1)
