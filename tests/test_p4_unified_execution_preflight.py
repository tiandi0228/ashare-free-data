import unittest
from collector.p4_unified_execution_preflight import assess
BASE=dict(issuer="sz.000089",entry_day="2026-10-23",exit_day="2026-10-26",
          calendar_sessions=["2026-10-23","2026-10-26"],issuer_status="TRADING",
          official_status_authenticated=True,official_calendar_authenticated=True,
          security_limit_authenticated=True,security_limit_up="7.00",security_limit_down="5.70",
          observed_low="6.30",observed_high="6.50",side="BUY",order_limit_price="6.40",
          orderbook_fill_evidence=True)
class UnifiedTests(unittest.TestCase):
 def test_all_evidence_only_admits_further_replay(self):
  r=assess(**BASE)
  self.assertTrue(r["candidate_for_independent_receipt_replay"])
  self.assertFalse(r["fill_certified"])
  self.assertEqual(r["orders"],[])
 def test_suspended_blocks(self):
  r=assess(**{**BASE,"issuer_status":"SUSPENDED"})
  self.assertIn("ISSUER_SUSPENDED_NO_EXECUTION",r["blocking_reasons"])
 def test_limit_up_blocks_buy(self):
  r=assess(**{**BASE,"security_limit_up":"6.40","observed_low":"6.40","observed_high":"6.40"})
  self.assertIn("LIMIT_UP_NO_FILL_ASSUMPTION",r["blocking_reasons"])
 def test_missing_price_limit_auth_blocks(self):
  r=assess(**{**BASE,"security_limit_authenticated":False})
  self.assertIn("SECURITY_PRICE_LIMIT_UNAUTHENTICATED",r["blocking_reasons"])
if __name__=="__main__":unittest.main()
