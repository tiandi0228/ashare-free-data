import unittest
from collector.p4_research_signal_lifecycle import advance
class LifecycleTests(unittest.TestCase):
 def test_unfilled_never_produces_return(self):
  x=advance(state="SIGNAL_READY",event="EXPIRE_UNFILLED",decision_day="2026-10-20",observation_day="2026-10-20")
  self.assertEqual(x["to_state"],"UNFILLED")
  self.assertFalse(x["net_returns_computed"])
  self.assertEqual(x["orders"],[])
 def test_entry_requires_post_decision_receipt(self):
  args=dict(state="SIGNAL_READY",event="OBSERVE_ENTRY",decision_day="2026-10-20",observation_day="2026-10-20",receipt_sha256="a"*64)
  with self.assertRaises(ValueError):advance(**args)
  args["observation_day"]="2026-10-21"
  self.assertEqual(advance(**args)["to_state"],"ENTRY_EVIDENCED")
 def test_no_exit_from_unfilled(self):
  with self.assertRaises(ValueError):
   advance(state="UNFILLED",event="OBSERVE_EXIT",decision_day="2026-10-20",observation_day="2026-10-21",receipt_sha256="b"*64)
if __name__=="__main__":unittest.main()
