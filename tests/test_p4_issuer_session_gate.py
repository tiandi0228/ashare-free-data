import unittest
from collector.p4_issuer_session_gate import check
BASE=dict(issuer="sz.000089",session_day="2026-10-26",official_calendar_sessions=["2026-10-26"],issuer_status="SUSPENDED",official_status_authenticated=True,official_calendar_authenticated=True)
class SessionGateTests(unittest.TestCase):
 def test_suspended_blocks_even_with_orderbook(self):
  r=check(**BASE,market_orderbook_evidence=True)
  self.assertEqual(r["outcome"],"ISSUER_SUSPENDED_NO_EXECUTION")
  self.assertFalse(r["fill_verified"])
 def test_missing_official_status_blocks(self):
  d={**BASE,"official_status_authenticated":False,"issuer_status":"TRADING"}
  self.assertEqual(check(**d)["outcome"],"ISSUER_STATUS_UNAUTHENTICATED")
 def test_unconfirmed_open_status_is_not_fill(self):
  d={**BASE,"issuer_status":"TRADING"}
  self.assertFalse(check(**d,market_orderbook_evidence=True)["fill_verified"])
 def test_calendar_missing_blocks(self):
  d={**BASE,"official_calendar_sessions":[]}
  self.assertEqual(check(**d)["outcome"],"MARKET_CLOSED_OR_SESSION_NOT_PROVEN")
if __name__=="__main__":unittest.main()
