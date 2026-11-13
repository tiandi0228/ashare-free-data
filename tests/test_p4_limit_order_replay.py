import unittest
from collector.p4_limit_order_replay import replay
BASE=dict(side="BUY",order_shares=200,limit_price="6.40",placed_at="2026-10-26T09:30:00+08:00",expires_at="2026-10-26T14:57:00+08:00")
def event(kind,time="2026-10-26T10:00:00+08:00",**kwargs):
 return {"kind":kind,"observed_at":time,"source_sha256":"a"*64,**kwargs}
class LimitTests(unittest.TestCase):
 def test_partial_fill_followed_by_cancel(self):
  q=replay(**BASE,events=[event("FILL_RECEIPT",shares=100,price="6.39"),dict(event("CANCEL_RECEIPT","2026-10-26T10:01:00+08:00"),source_sha256="b"*64)])
  self.assertEqual((q["receipt_fill_shares"],q["unfilled_shares"]),(100,100))
  self.assertEqual(q["terminal_state"],"CANCELLED_PARTIAL")
  self.assertFalse(q["fees_finalized"])
 def test_above_limit_rejected(self):
  with self.assertRaises(ValueError):replay(**BASE,events=[event("FILL_RECEIPT",shares=100,price="6.41")])
 def test_overfill_rejected(self):
  with self.assertRaises(ValueError):replay(**BASE,events=[event("FILL_RECEIPT",shares=300,price="6.39")])
 def test_fill_after_cancel_rejected(self):
  with self.assertRaises(ValueError):replay(**BASE,events=[event("CANCEL_RECEIPT"),event("FILL_RECEIPT","2026-10-26T11:00:00+08:00",shares=100,price="6.39")])
 def test_duplicate_fill_receipt_rejected_even_if_time_changes(self):
  first=event("FILL_RECEIPT",shares=100,price="6.39")
  second=dict(first,observed_at="2026-10-26T10:01:00+08:00")
  with self.assertRaisesRegex(ValueError,"duplicate event receipt"):
   replay(**BASE,events=[first,second])
  distinct=dict(second,source_sha256="b"*64)
  q=replay(**BASE,events=[first,distinct])
  self.assertEqual(q["receipt_fill_shares"],200)
  self.assertFalse(q["real_fill_certified"])
  self.assertEqual(q["trade_gate"],"BLOCKED")
 def test_fill_and_cancel_cannot_share_one_digest(self):
  first=event("FILL_RECEIPT",shares=100,price="6.39")
  with self.assertRaisesRegex(ValueError,"duplicate event receipt"):
   replay(**BASE,events=[first,event("CANCEL_RECEIPT")])
 def test_unfilled_does_not_invent_pnl(self):
  q=replay(**BASE,events=[])
  self.assertIsNone(q["weighted_fill_price"])
  self.assertEqual(q["orders"],[])
if __name__=="__main__":unittest.main()
