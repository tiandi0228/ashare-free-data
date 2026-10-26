import unittest
from collector.p4_cancel_replace_audit import review
def base(quantity=200):
 return dict(side="BUY",order_shares=quantity,limit_price="6.40",
 placed_at="2026-10-26T09:30:00+08:00",expires_at="2026-10-26T14:55:00+08:00",
 events=[dict(kind="FILL_RECEIPT",observed_at="2026-10-26T09:31:00+08:00",shares=100,price="6.39",source_sha256="a"*64),
 dict(kind="CANCEL_RECEIPT",observed_at="2026-10-26T09:32:00+08:00",source_sha256="b"*64)])
def new(quantity=100):
 return dict(side="BUY",order_shares=quantity,limit_price="6.38",
 placed_at="2026-10-26T09:33:00+08:00",expires_at="2026-10-26T14:55:00+08:00",
 events=[dict(kind="FILL_RECEIPT",observed_at="2026-10-26T09:34:00+08:00",shares=100,price="6.38",source_sha256="c"*64)])
class Tests(unittest.TestCase):
 def test_valid_replacement(self):
  x=review(original=base(),replacement=new())
  self.assertEqual(x["aggregate_receipt_fill_shares"],200)
  self.assertEqual(x["orders"],[])
 def test_reject_overcommit(self):
  with self.assertRaises(ValueError):review(original=base(),replacement=new(200))
 def test_reject_missing_cancel_ack(self):
  x=base();x["events"]=x["events"][:1]
  with self.assertRaises(ValueError):review(original=x,replacement=new())
 def test_reject_early_replacement(self):
  x=new();x["placed_at"]="2026-10-26T09:31:30+08:00"
  with self.assertRaises(ValueError):review(original=base(),replacement=x)
if __name__=="__main__":unittest.main()
