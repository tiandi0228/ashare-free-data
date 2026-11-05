"""Independent accounting reconciliation for synthetic P4 partial executions.

Audits a *separate* synthetic kernel report against its explicit fixture input.
Does not consume broker orders, historical vendor OHLC, or infer exchange fills.
"""
from decimal import Decimal, InvalidOperation
from collector.p4_synthetic_t1_execution_kernel import (
    PROVENANCE, PHASE as KERNEL_PHASE, replay, costs, price, CAPITAL,
)

PHASE="P4_SYNTHETIC_PARTIAL_FILL_INDEPENDENT_RECONCILIATION"

def reconcile(fixture, report):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],
          "real_broker_fills":0,"broker_fill_authentication":False,
          "exchange_queue_authenticated":False,
          "historical_PIT_verified":False,
          "historical_OOS_validated":False,
          "trade_authorized":False,
          "synthetic_only":True}
    def fail(reason): return dict(base,reason=reason)
    if (not isinstance(fixture,dict) or fixture.get("provenance")!=PROVENANCE
        or fixture.get("trade_gate")!="BLOCKED"
        or not isinstance(report,dict) or report.get("phase")!=KERNEL_PHASE
        or report.get("trade_gate")!="BLOCKED"
        or report.get("status")!="SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED"
        or report.get("orders")!=[] or report.get("executable_candidates")!=[]
        or report.get("historical_PIT_verified") is not False
        or report.get("real_broker_fills")!=0):
        return fail("UNSAFE_OR_INCOMPLETE_SYNTHETIC_REPORT")
    # Independent kernel pass disallows a forged external report with the
    # same final cash but different fills, Friday risk, or cancelled orders.
    expected=replay(fixture)
    if expected.get("status")!="SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED":
        return fail("SYNTHETIC_FIXTURE_NOT_ACCEPTED")
    expected_keys=(
        "synthetic_fills","synthetic_fill_count",
        "synthetic_cash_end_cny","synthetic_position_shares",
        "synthetic_sellable_shares","synthetic_open_order_remaining_shares",
        "synthetic_friday_close_reports","synthetic_friday_unattested_session_count",
        "synthetic_rejections","synthetic_last_session_end_explicit",
        "real_broker_orders","real_broker_fills",
    )
    if any(report.get(key)!=expected.get(key) for key in expected_keys):
        return fail("KERNEL_REPORT_VS_FIXTURE_MISMATCH")
    fills=report["synthetic_fills"]
    try:
        shares=0
        cash=CAPITAL
        buy_qty=sell_qty=0
        gross_buy=gross_sell=Decimal("0")
        for row in fills:
            kind=row["kind"]
            qty=row["synthetic_quantity"]
            px=price(row["synthetic_price"])
            if (type(qty) is not int or qty<=0 or
                kind not in ("FILL_BUY","FILL_SELL") or
                row.get("real_exchange_execution") is not False or
                row.get("real_broker_execution") is not False):
                return fail("INVALID_SYNTHETIC_FILL_LEDGER")
            notional=qty*px
            if kind=="FILL_BUY":
                buy_qty+=qty;shares+=qty;gross_buy+=notional
                cash-=notional+costs(qty,px,"BUY",fixture["issuer"])
            else:
                sell_qty+=qty;shares-=qty;gross_sell+=notional
                cash+=notional-costs(qty,px,"SELL",fixture["issuer"])
            if shares<0 or cash<0:
                return fail("NEGATIVE_LEDGER_BALANCE")
        if (shares!=report["synthetic_position_shares"] or
            cash.quantize(Decimal("0.01"))!=Decimal(report["synthetic_cash_end_cny"]) or
            len(fills)!=report["synthetic_fill_count"]):
            return fail("INDEPENDENT_ACCOUNTING_MISMATCH")
        if (report["synthetic_sellable_shares"]>shares or
            report["synthetic_open_order_remaining_shares"]<0):
            return fail("INVALID_REMAINING_SHARE_STATE")
    except (ValueError,TypeError,KeyError,InvalidOperation,ArithmeticError):
        return fail("MALFORMED_SYNTHETIC_LEDGER")
    return dict(base,status="SYNTHETIC_PARTIAL_FILL_RECONCILED_NOT_EXECUTION_PROOF",
                source_provenance=PROVENANCE,
                synthetic_fill_count=len(fills),
                synthetic_buy_shares=buy_qty,
                synthetic_sell_shares=sell_qty,
                synthetic_position_shares=shares,
                synthetic_sellable_shares=report["synthetic_sellable_shares"],
                synthetic_open_order_remaining_shares=report["synthetic_open_order_remaining_shares"],
                synthetic_gross_buy_cny=str(gross_buy.quantize(Decimal("0.01"))),
                synthetic_gross_sell_cny=str(gross_sell.quantize(Decimal("0.01"))),
                synthetic_cash_end_cny=str(cash.quantize(Decimal("0.01"))),
                synthetic_friday_close_reports=report["synthetic_friday_close_reports"],
                real_exchange_fills_authenticated=0,
                historical_execution_certified=False)

def contract_summary():
    return {"phase":PHASE,"trade_gate":"BLOCKED","orders":[],
            "executable_candidates":[],"verified_broker_fills":0,
            "synthetic_partial_accounting_available":True,
            "real_partial_fill_provenance_verified":False,
            "historical_PIT_verified":False}
