import unittest
from collector.p4_time_exit_unresolved import assess
PRE=dict(phase="P4_UNIFIED_EXECUTION_RESEARCH_PREFLIGHT",trade_gate="BLOCKED",fill_certified=False,orders=[],candidate_for_independent_receipt_replay=True)
DATES=["2026-10-19","2026-10-20","2026-10-21","2026-10-22","2026-10-23","2026-10-26","2026-10-27"]
def case(day,pre=PRE,receipt=False):
 return assess(entry_day=DATES[0],observation_day=day,calendar_sessions=DATES,preflight=pre,receipt_verified=receipt)
class Tests(unittest.TestCase):
 def test_d3_without_receipt(self):
  r=case(DATES[3]);self.assertEqual(r["state"],"EXIT_RECEIPT_MISSING_UNRESOLVED");self.assertFalse(r["return_finalized"])
 def test_d6_remains_open_and_not_fake_exit(self):
  r=case(DATES[6]);self.assertEqual(r["state"],"FRIDAY_EXIT_OVERDUE_UNRESOLVED");self.assertEqual(r["orders"],[])
 def test_blocked_d5(self):
  p={**PRE,"candidate_for_independent_receipt_replay":False}
  self.assertEqual(case(DATES[5],pre=p)["state"],"FRIDAY_EXIT_OVERDUE_BLOCKED")
 def test_friday_forces_early_exit_even_on_d1(self):
  r=assess(entry_day="2026-10-22",observation_day="2026-10-23",
           calendar_sessions=["2026-10-22","2026-10-23"],
           preflight=PRE)
  self.assertTrue(r["friday_mandatory_exit_due"])
  self.assertEqual(r["sessions_elapsed"],1)
  self.assertEqual(r["state"],"EXIT_RECEIPT_MISSING_UNRESOLVED")
 def test_friday_buy_is_not_eligible_under_frozen_rule(self):
  with self.assertRaises(ValueError):
   assess(entry_day="2026-10-23",observation_day="2026-10-26",
          calendar_sessions=["2026-10-23","2026-10-26"],
          preflight=PRE)
 def test_before_d3(self):
  self.assertEqual(case(DATES[1])["state"],"BEFORE_TIME_EXIT_WINDOW")
if __name__=="__main__":unittest.main()
