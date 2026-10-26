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
  self.assertEqual(advance(**args)["to_state"],"ENTRY_EVIDENCED")
  args["observation_day"]="2026-10-20"
  self.assertEqual(advance(**args)["to_state"],"ENTRY_EVIDENCED")
 def test_exit_enforces_tplus1_from_actual_entry(self):
  args=dict(state="ENTRY_EVIDENCED",event="OBSERVE_EXIT",decision_day="2026-10-20",entry_day="2026-10-21",observation_day="2026-10-21",receipt_sha256="b"*64)
  with self.assertRaises(ValueError):advance(**args)
  args["observation_day"]="2026-10-22"
  self.assertEqual(advance(**args)["to_state"],"EXIT_EVIDENCED")
 def test_entry_after_validity_expires_is_rejected(self):
  with self.assertRaises(ValueError):
   advance(state="SIGNAL_READY",event="OBSERVE_ENTRY",decision_day="2026-10-20",observation_day="2026-10-22",valid_until_day="2026-10-21",receipt_sha256="c"*64)
 def test_expiry_cannot_happen_before_deadline(self):
  with self.assertRaises(ValueError):
   advance(state="SIGNAL_READY",event="EXPIRE_UNFILLED",decision_day="2026-10-20",observation_day="2026-10-20",valid_until_day="2026-10-21")
 def test_no_exit_from_unfilled(self):
  with self.assertRaises(ValueError):
   advance(state="UNFILLED",event="OBSERVE_EXIT",decision_day="2026-10-20",observation_day="2026-10-21",receipt_sha256="b"*64)
if __name__=="__main__":unittest.main()
