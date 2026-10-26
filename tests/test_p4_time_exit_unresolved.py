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
  r=case(DATES[6]);self.assertEqual(r["state"],"OVERDUE_RECEIPT_MISSING");self.assertEqual(r["orders"],[])
 def test_blocked_d5(self):
  p={**PRE,"candidate_for_independent_receipt_replay":False}
  self.assertEqual(case(DATES[5],pre=p)["state"],"EXIT_BLOCKED_UNRESOLVED")
 def test_before_d3(self):
  self.assertEqual(case(DATES[1])["state"],"BEFORE_TIME_EXIT_WINDOW")
if __name__=="__main__":unittest.main()
