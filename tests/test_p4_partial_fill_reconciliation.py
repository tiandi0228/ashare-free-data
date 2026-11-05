"""Independent P4 fixture accounting, not observed or broker fills."""
import copy
import unittest
from collector.p4_synthetic_t1_execution_kernel import replay,PROVENANCE
from collector.p4_partial_fill_reconciliation import reconcile,contract_summary
MON="2026-11-02"
TUE="2026-11-03"
FRI="2026-11-06"
def e(session,kind,**params): return {"session":session,"kind":kind,**params}
def fixture():
    return {"provenance":PROVENANCE,"issuer":"sh.600000","trade_gate":"BLOCKED",
            "orders":[],"historical_PIT_verified":False,
            "real_liquidity_authenticated":False,"events":[
        e(MON,"BEGIN_SESSION"),
        e(MON,"PLACE_BUY",quantity=100,limit_price="10.00"),
        e(MON,"FILL_BUY",quantity=40,fill_price="9.99",origin="SYNTHETIC_MATCHING_FIXTURE"),
        e(MON,"FILL_BUY",quantity=60,fill_price="10.00",origin="SYNTHETIC_MATCHING_FIXTURE"),
        e(TUE,"BEGIN_SESSION"),
        e(TUE,"PLACE_SELL",quantity=100,limit_price="9.80",reason="FROZEN_STOP"),
        e(TUE,"FILL_SELL",quantity=30,fill_price="9.82",origin="SYNTHETIC_MATCHING_FIXTURE"),
        e(TUE,"CANCEL"),
    ]}
class PartialReconciliationTests(unittest.TestCase):
    def test_partial_fills_and_cancel_remain_unfilled(self):
        x=fixture();q=reconcile(x,replay(x))
        self.assertEqual(q["status"],"SYNTHETIC_PARTIAL_FILL_RECONCILED_NOT_EXECUTION_PROOF")
        self.assertEqual(q["synthetic_fill_count"],3)
        self.assertEqual(q["synthetic_buy_shares"],100)
        self.assertEqual(q["synthetic_sell_shares"],30)
        self.assertEqual(q["synthetic_position_shares"],70)
        self.assertEqual(q["synthetic_open_order_remaining_shares"],0)
        self.assertEqual(q["real_exchange_fills_authenticated"],0)
        self.assertEqual(q["trade_gate"],"BLOCKED")
        self.assertEqual(q["orders"],[])
    def test_unresolved_sell_and_friday_risk_not_hidden(self):
        x=fixture();x["events"][-1]=e(FRI,"BEGIN_SESSION")
        x["events"].extend([
            e(FRI,"PLACE_SELL",quantity=70,limit_price="9.50",reason="FRIDAY_FORCE"),
            e(FRI,"END_SESSION")])
        # Original Tuesday open sell must be explicitly cancelled before
        # Friday; this intentionally invalid fixture never authenticates exit.
        q=reconcile(x,replay(x))
        self.assertEqual(q["status"],"REJECTED")
    def test_forged_partial_receipt_or_fee_is_rejected(self):
        x=fixture();valid=replay(x)
        for tamper in (
            lambda v:v["synthetic_fills"][0].update(synthetic_quantity=41),
            lambda v:v.update(synthetic_cash_end_cny="9000.00"),
            lambda v:v.update(synthetic_position_shares=0),
            lambda v:v.update(synthetic_open_order_remaining_shares=100),
            lambda v:v.update(synthetic_sellable_shares=999),
            lambda v:v.update(real_broker_fills=1),
            lambda v:v.update(trade_gate="OPEN"),
        ):
            with self.subTest(tamper=tamper):
                report=copy.deepcopy(valid);tamper(report)
                q=reconcile(x,report)
                self.assertEqual(q["status"],"REJECTED")
                self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_real_source_is_never_allowed(self):
        x=fixture();r=replay(x)
        x["provenance"]="VENDOR_REAL_BARS"
        q=reconcile(x,r)
        self.assertEqual(q["status"],"REJECTED")
    def test_contract_cannot_prove_market_execution(self):
        q=contract_summary()
        self.assertFalse(q["real_partial_fill_provenance_verified"])
        self.assertEqual(q["verified_broker_fills"],0)
        self.assertEqual(q["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
