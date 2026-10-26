import unittest
from collector.p4_v22_cycle_audit import audit

DAYS=["2026-10-19","2026-10-20","2026-10-21","2026-10-22","2026-10-23","2026-10-26","2026-10-27"]
def order(side,day,n=100,fills=100):
    return {"side":side,"order_shares":n,"limit_price":"6.40",
            "placed_at":day+"T09:30:00+08:00",
            "expires_at":day+"T14:55:00+08:00",
            "events":([{"kind":"FILL_RECEIPT","shares":fills,"price":"6.40",
                        "observed_at":day+"T10:00:00+08:00",
                        "source_sha256":"a"*64}] if fills else [])}
MARKET={"issuer_status":"TRADING",
        "official_status_authenticated":True,
        "official_calendar_authenticated":True,
        "security_limit_authenticated":True,
        "security_limit_up":"7.00","security_limit_down":"5.70",
        "observed_low":"6.30","observed_high":"6.50",
        "order_limit_price":"6.40","orderbook_fill_evidence":True}
def args(**changes):
    d=dict(issuer="sz.000089",buy_order=order("BUY",DAYS[0]),
           sell_order=order("SELL",DAYS[3]),asof_day=DAYS[3],
           calendar_sessions=DAYS,exit_market_inputs=MARKET,
           planned_stop_price="6.35")
    d.update(changes)
    return d
class CycleTests(unittest.TestCase):
    def test_observed_exit_is_not_certified_pnl(self):
        x=audit(**args())
        self.assertEqual(x["remaining_shares"],0)
        self.assertEqual(x["position_state"],"EXIT_RECEIPT_OBSERVED_UNCERTIFIED")
        self.assertFalse(x["modeled_net_pnl_finalized"])
        self.assertFalse(x["fill_certified"])
        self.assertEqual(x["orders"],[])
    def test_missing_exit_d6_remains_unresolved(self):
        x=audit(**args(sell_order=None,asof_day=DAYS[6]))
        self.assertEqual(x["position_state"],"FRIDAY_EXIT_OVERDUE_UNRESOLVED")
        self.assertTrue(x["friday_deadline_breached"])
        self.assertEqual(x["remaining_shares"],100)
    def test_partial_sell_keeps_position_open(self):
        buy=order("BUY",DAYS[0],n=200,fills=200)
        x=audit(**args(buy_order=buy,sell_order=order("SELL",DAYS[3],fills=100)))
        self.assertEqual(x["position_state"],"PARTIAL_EXIT_REMAINDER_UNRESOLVED")
        self.assertEqual(x["remaining_shares"],100)
    def test_suspension_conflicts_with_sell_receipt(self):
        x=audit(**args(exit_market_inputs={**MARKET,"issuer_status":"SUSPENDED"}))
        self.assertTrue(x["receipt_conflicts_with_market_preflight"])
        self.assertFalse(x["fill_certified"])
    def test_excessive_stop_risk_is_not_approved(self):
        x=audit(**args(planned_stop_price="6.10"))
        self.assertFalse(x["planned_stop_within_3pct_budget"])
        self.assertEqual(x["executable_candidates"],[])
    def test_same_day_sale_rejected(self):
        with self.assertRaises(ValueError):
            audit(**args(sell_order=order("SELL",DAYS[0]),asof_day=DAYS[0]))
    def test_unfilled_entry_excluded(self):
        x=audit(**args(buy_order=order("BUY",DAYS[0],fills=0),sell_order=None))
        self.assertEqual(x["position_state"],"UNFILLED_ENTRY_EXCLUDED_FROM_RETURNS")
    def test_future_sell_order_rejected(self):
        with self.assertRaises(ValueError):
            audit(**args(sell_order=order("SELL", DAYS[6])))
    def test_sell_limit_must_match_preflight(self):
        with self.assertRaises(ValueError):
            audit(**args(exit_market_inputs={**MARKET,"order_limit_price":"6.35"}))
    def test_conflicting_market_date_rejected(self):
        with self.assertRaises(ValueError):
            audit(**args(exit_market_inputs={**MARKET,"exit_day":DAYS[2]}))
if __name__=="__main__":
    unittest.main()
