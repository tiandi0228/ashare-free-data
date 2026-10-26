import unittest
from collector.p4_partial_fill_fee_inventory import summarize
def order(side,day,qty=200,price="6.40",fills=100):
 time=day+"T09:30:00+08:00"
 return dict(side=side,order_shares=qty,limit_price=price,placed_at=time,expires_at=day+"T14:55:00+08:00",
 events=[dict(kind="FILL_RECEIPT",observed_at=day+"T10:00:00+08:00",shares=fills,price=price,source_sha256="a"*64)])
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
 def test_unfilled_cannot_be_sold(self):
  b=order("BUY","2026-10-26");b["events"]=[]
  with self.assertRaises(ValueError):summarize(buy_order=b,sell_order=order("SELL","2026-10-27",qty=100,fills=100))
if __name__=="__main__":unittest.main()
