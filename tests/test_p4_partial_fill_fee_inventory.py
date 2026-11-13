import unittest
from collector.p4_partial_fill_fee_inventory import summarize
def order(side,day,qty=200,price="6.40",fills=100):
 time=day+"T09:30:00+08:00"
 return dict(side=side,order_shares=qty,limit_price=price,placed_at=time,expires_at=day+"T14:55:00+08:00",
 events=[dict(kind="FILL_RECEIPT",observed_at=day+"T10:00:00+08:00",shares=fills,price=price,source_sha256=("a" if side=="BUY" else "c")*64)])
class InventoryTests(unittest.TestCase):
 def test_partial_buy_min_commission_once(self):
  q=summarize(buy_order=order("BUY","2026-10-26",fills=100))
  self.assertEqual(q["observed_buy_shares"],100)
  self.assertEqual(q["buy_fees_model"],"5.01")
  self.assertEqual(q["inventory_shares"],100)
 def test_same_day_exit_rejected(self):
  with self.assertRaises(ValueError):summarize(buy_order=order("BUY","2026-10-26",fills=100),sell_order=order("SELL","2026-10-26",qty=100,fills=100))
 def test_next_day_exit_and_sell_tax(self):
  q=summarize(buy_order=order("BUY","2026-10-26",fills=100),sell_order=order("SELL","2026-10-27",qty=100,fills=100))
  self.assertEqual(q["inventory_shares"],0)
  self.assertEqual(q["sell_fees_model"],"5.33")
 def test_same_beijing_day_rejected_with_mixed_offset_labels(self):
  b=order("BUY","2026-10-26")
  b["events"][0]["observed_at"]="2026-10-25T22:00:00-04:00"
  s=order("SELL","2026-10-26",qty=100)
  with self.assertRaisesRegex(ValueError,"T\\+1 available"):
   summarize(buy_order=b,sell_order=s)
 def test_mixed_offset_partial_sells_use_chronological_inventory(self):
  b=order("BUY","2026-10-26",qty=200,fills=200)
  s=order("SELL","2026-10-27")
  s["events"][0]["observed_at"]="2026-10-27T02:00:00Z"
  s["events"].append(dict(s["events"][0],observed_at="2026-10-27T10:01:00+08:00",source_sha256="b"*64))
  q=summarize(buy_order=b,sell_order=s)
  self.assertEqual((q["observed_sell_shares"],q["inventory_shares"]),(200,0))
  self.assertFalse(q["receipt_fill_certified"])
 def test_cross_order_reuse_rejected_before_inventory_or_fees(self):
  for kind in ("FILL_RECEIPT","CANCEL_RECEIPT"):
   with self.subTest(kind=kind):
    b=order("BUY","2026-10-26")
    s=order("SELL","2026-10-27",qty=100)
    digest=b["events"][0]["source_sha256"]
    if kind=="FILL_RECEIPT":
     s["events"][0]["source_sha256"]=digest
    else:
     s["events"]=[dict(kind=kind,observed_at="2026-10-27T10:01:00+08:00",
                       source_sha256=digest)]
    with self.assertRaisesRegex(ValueError,"receipt reused across buy and sell"):
     summarize(buy_order=b,sell_order=s)
 def test_unfilled_cannot_be_sold(self):
  b=order("BUY","2026-10-26");b["events"]=[]
  with self.assertRaises(ValueError):summarize(buy_order=b,sell_order=order("SELL","2026-10-27",qty=100,fills=100))
if __name__=="__main__":unittest.main()
