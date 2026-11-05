"""Synthetic-only P4 order state machine: no historical/real orders or fills.

Works ONLY with explicitly labelled offline fixture events; the events contain
invented liquidity and synthetic confirmations and may never be interpreted as
exchange or broker fill receipts. A real vendor CSV can NEVER drive this kernel.

Models buy lots (initial buy >=100 and multiple of 100), partial executions,
limit price protections, cash fees, same-session T+1 unavailable inventory,
next synthetic session settlement, odd-lot final liquidation, cancelling
unfilled orders, and Friday-forced-exit failures. Every output keeps
trade_gate=BLOCKED, zero real trades and historical PIT/OOS false.
"""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

from collector.p4_observed_fee_friction import (
    CAPITAL, CENT, COMMISSION, COMMISSION_FLOOR, STAMP_ON_SELL, SH_TRANSFER
)

PHASE="P4_SYNTHETIC_T1_PARTIAL_FILL_CONTRACT"
PROVENANCE="SYNTHETIC_OFFLINE_FIXTURE_ONLY"
ISSUER=re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
MAX_EVENTS=80
KIND={"BEGIN_SESSION","END_SESSION","PLACE_BUY","FILL_BUY","PLACE_SELL","FILL_SELL","CANCEL"}
SELL_REASONS={"FROZEN_STOP","FROZEN_TARGET","TIME_EXIT","FRIDAY_FORCE"}
MAX_QUANTITY=10000


def price(value):
    if not isinstance(value,str):
        raise ValueError("non-string fixture price")
    x=Decimal(value)
    if (not x.is_finite() or x<=0 or x!=x.quantize(CENT)):
        raise ValueError("synthetic price must be positive 0.01 tick")
    return x


def _integer(value):
    if type(value) is not int or not 0<value<=MAX_QUANTITY:
        raise ValueError("invalid synthetic share count")
    return value


def _fee(value):
    return (value*COMMISSION).quantize(CENT,rounding=ROUND_HALF_UP)


def costs(qty, px, side, issuer):
    notional=Decimal(qty)*px
    commission=max(COMMISSION_FLOOR,_fee(notional))
    transfer=(notional*SH_TRANSFER).quantize(
        CENT,rounding=ROUND_HALF_UP) if issuer.startswith("sh.") else Decimal(0)
    stamp=(notional*STAMP_ON_SELL).quantize(
        CENT,rounding=ROUND_HALF_UP) if side=="SELL" else Decimal(0)
    return commission+transfer+stamp


def _day(raw):
    if not isinstance(raw,str):
        raise ValueError("synthetic session not canonical")
    x=date.fromisoformat(raw)
    if x.isoformat()!=raw or x.weekday()>=5:
        raise ValueError("invalid synthetic weekday session")
    return x


def replay(fixture):
    base={
        "phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
        "real_broker_orders":0,"real_broker_fills":0,
        "exchange_queue_authenticated":False,
        "historical_calendar_asof_authenticated":False,
        "historical_PIT_verified":False,"historical_OOS_validated":False,
        "strategy_backtest_certified":False,"trade_authorized":False,
        "synthetic_not_historical_execution":True,
        "cash_start_cny":str(CAPITAL),
    }
    def fail(reason):
        return dict(base,reason=reason)
    try:
        if (not isinstance(fixture,dict)
                or fixture.get("provenance")!=PROVENANCE
                or fixture.get("trade_gate")!="BLOCKED"
                or fixture.get("orders")!=[]
                or fixture.get("broker_order_id") is not None
                or fixture.get("broker_execution_id") is not None
                or fixture.get("historical_PIT_verified") is not False
                or fixture.get("real_liquidity_authenticated") is not False):
            return fail("REAL_OR_UNSAFE_SOURCE_NOT_ACCEPTED")
        issuer=fixture.get("issuer")
        events=fixture.get("events")
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
                or not isinstance(events,list)
                or not 1<=len(events)<=MAX_EVENTS):
            return fail("UNBOUNDED_OR_INVALID_FIXTURE")
        cash=CAPITAL
        held=0
        sellable=0
        pending=None
        day=None
        session_ended=False
        friday_force_order_accepted=False
        friday_closure_reports=[]
        friday_unattested_prior_sessions=0
        synthetic_fills=[]
        rejected=[]  # hypothetical rejection evidence, no actual orders
        for ev in events:
            if not isinstance(ev,dict) or ev.get("kind") not in KIND:
                return fail("UNKNOWN_SYNTHETIC_EVENT")
            kind=ev["kind"]
            stamp=_day(ev.get("session"))
            if kind=="BEGIN_SESSION":
                if day is not None and stamp<=day:
                    return fail("NON_MONOTONIC_SYNTHETIC_SESSION")
                # A Friday position cannot silently roll into Monday without
                # an explicit end-of-session snapshot of its residual risk.
                if (day is not None and day.weekday()==4 and
                        held>0 and not session_ended):
                    return fail("FRIDAY_POSITION_ROLLED_WITHOUT_CLOSE_RISK_SNAPSHOT")
                if day is not None and day.weekday()==4 and not session_ended:
                    friday_unattested_prior_sessions+=1
                if pending is not None:
                    # Do not automatically fill or cancel a day order.
                    # Explicit cancel at end-of-day required.
                    return fail("OPEN_ORDER_CARRIED_WITHOUT_EXPLICIT_POLICY")
                day=stamp
                sellable=held
                session_ended=False
                friday_force_order_accepted=False
                continue
            if day is None or stamp!=day:
                return fail("EVENT_NOT_IN_ACTIVE_SYNTHETIC_SESSION")
            if session_ended:
                return fail("EVENT_AFTER_EXPLICIT_SYNTHETIC_SESSION_END")
            if kind=="END_SESSION":
                # End-of-session is a synthetic marker, NOT a closing auction
                # execution and NOT a certified exchange session boundary.
                if stamp.weekday()==4:
                    if held==0 and pending is None:
                        outcome="SYNTHETIC_FRIDAY_FLAT_NOT_REAL_EXIT_PROOF"
                    elif pending is not None and pending["side"]=="SELL":
                        outcome="SYNTHETIC_FRIDAY_UNFILLED_SELL_REMAINDER"
                    elif friday_force_order_accepted:
                        outcome="SYNTHETIC_FRIDAY_RESIDUAL_AFTER_EXIT_ATTEMPT"
                    else:
                        outcome="SYNTHETIC_FRIDAY_POSITION_WITHOUT_ACCEPTED_FORCE_EXIT"
                    friday_closure_reports.append({
                        "synthetic_friday_date":day.isoformat(),
                        "synthetic_close_status":outcome,
                        "unliquidated_shares":held,
                        "tplus1_sellable_at_close":sellable,
                        "open_sell_order_remaining_shares":(
                            pending["remaining"]
                            if pending and pending["side"]=="SELL" else 0),
                        "accepted_friday_force_sell_order":
                            friday_force_order_accepted,
                        "real_friday_exit_fill_authenticated":False,
                        "real_exchange_closing_time_authenticated":False,
                    })
                    if held>0:
                        rejected.append("FRIDAY_FLAT_POSITION_POLICY_BREACH_SYNTHETIC")
                session_ended=True
                continue
            if kind=="PLACE_BUY":
                if day.weekday()==4:
                    rejected.append("FRIDAY_NEW_BUY_BLOCKED_BY_FROZEN_POLICY")
                    continue
                if pending is not None or held!=0:
                    return fail("ONE_POSITION_OR_PENDING_ORDER_LIMIT")
                qty=_integer(ev.get("quantity"))
                if qty%100!=0:
                    return fail("INITIAL_A_SHARE_BUY_ORDER_NOT_100_SHARE_LOT")
                limit=price(ev.get("limit_price"))
                if Decimal(qty)*limit+costs(qty,limit,"BUY",issuer)>cash:
                    rejected.append("BUY_BUDGET_WITH_FULL_LIMIT_RESERVE")
                    continue
                pending={"side":"BUY","remaining":qty,"limit":limit,
                         "reason":"SYNTHETIC_FIXTURE_BUY"}
                continue
            if kind=="PLACE_SELL":
                if pending is not None:
                    return fail("PENDING_ORDER_NOT_RESOLVED")
                qty=_integer(ev.get("quantity"))
                if ev.get("reason") not in SELL_REASONS:
                    return fail("INVALID_FROZEN_EXIT_REASON")
                if qty>sellable:
                    rejected.append("TPLUS1_OR_INSUFFICIENT_SELLABLE_POSITION")
                    continue
                if qty%100!=0 and qty!=held:
                    return fail("NONFINAL_ODD_LOT_SELL_NOT_ALLOWED")
                pending={"side":"SELL","remaining":qty,
                         "limit":price(ev.get("limit_price")),
                         "reason":ev["reason"]}
                if day.weekday()==4 and ev["reason"]=="FRIDAY_FORCE":
                    friday_force_order_accepted=True
                continue
            if kind=="CANCEL":
                if pending is None:
                    return fail("NO_PENDING_SYNTHETIC_ORDER")
                pending=None
                continue
            if kind not in ("FILL_BUY","FILL_SELL"):
                return fail("UNKNOWN_SYNTHETIC_EVENT")
            side="BUY" if kind=="FILL_BUY" else "SELL"
            if pending is None or pending["side"]!=side:
                return fail("SYNTHETIC_FILL_WITHOUT_MATCHING_ORDER")
            if ev.get("origin")!="SYNTHETIC_MATCHING_FIXTURE":
                return fail("UNAUTHENTICATED_FILL_ORIGIN")
            qty=_integer(ev.get("quantity"))
            px=price(ev.get("fill_price"))
            if qty>pending["remaining"]:
                return fail("OVERFILL_SYNTHETIC_ORDER")
            if side=="BUY":
                if px>pending["limit"]:
                    return fail("BUY_EXECUTED_ABOVE_LIMIT")
                charge=Decimal(qty)*px+costs(qty,px,side,issuer)
                if charge>cash:
                    return fail("INSUFFICIENT_CASH_AT_SYNTHETIC_FILL")
                cash-=charge
                held+=qty
                # Buy shares cannot be sold in this same synthetic session.
            else:
                if px<pending["limit"]:
                    return fail("SELL_EXECUTED_BELOW_LIMIT")
                if qty>sellable or qty>held:
                    return fail("SELL_EXCEEDS_TPLUS1_AVAILABLE")
                cash+=Decimal(qty)*px-costs(qty,px,side,issuer)
                held-=qty
                sellable-=qty
            pending["remaining"]-=qty
            synthetic_fills.append({
                "session":day.isoformat(),"kind":kind,
                "synthetic_quantity":qty,
                "synthetic_price":str(px),
                "real_exchange_execution":False,
                "real_broker_execution":False,
            })
            if pending["remaining"]==0:
                pending=None
        if day is None:
            return fail("MISSING_SYNTHETIC_SESSION")
        if held<0 or sellable<0 or sellable>held or cash<0:
            return fail("BROKEN_SYNTHETIC_LEDGER_CONSERVATION")
        if pending is not None:
            rejected.append("UNRESOLVED_SYNTHETIC_ORDER_NOT_A_FILL")
        if (day.weekday()==4 and not session_ended):
            rejected.append("LAST_FRIDAY_CLOSE_SNAPSHOT_NOT_OBSERVED")
        return dict(base,
            status="SYNTHETIC_ONLY_TPLUS1_AND_PARTIAL_ORDER_STATE_TESTED",
            fixture_session_count=len({x["session"] for x in events}),
            fixture_event_count=len(events),
            synthetic_fill_count=len(synthetic_fills),
            synthetic_fills=synthetic_fills,
            synthetic_open_order_remaining_shares=(
                pending["remaining"] if pending else 0),
            synthetic_position_shares=held,
            synthetic_sellable_shares=sellable,
            synthetic_cash_end_cny=str(cash.quantize(CENT)),
            synthetic_rejections=rejected,
            synthetic_friday_close_reports=friday_closure_reports,
            synthetic_friday_close_report_count=len(friday_closure_reports),
            synthetic_friday_unattested_session_count=(
                friday_unattested_prior_sessions+
                int(day.weekday()==4 and not session_ended)),
            synthetic_all_friday_sessions_proven_flat_in_fixture=(
                bool(friday_closure_reports)
                and friday_unattested_prior_sessions==0
                and not (day.weekday()==4 and not session_ended)
                and all(x["unliquidated_shares"]==0 and
                        x["open_sell_order_remaining_shares"]==0
                        for x in friday_closure_reports)),
            synthetic_last_session_end_explicit=session_ended,
            real_friday_exit_authentication_count=0,
            real_exchange_session_end_authenticated=False,
            real_friday_liquidation_certified=False,
            frozen_strategy_entry_criteria_verified=False,
            historical_broker_trade_evidence_available=False,
            real_order_fill_assumed=False,
            limitations=[
                "SYNTHETIC_MATCHING_FIXTURE_IS_NOT_HISTORICAL_ORDER_BOOK",
                "BROKER_OR_EXCHANGE_TRADE_IDS_ARE_NOT_AUTHENTICATED",
                "REAL_PRICE_LIMIT_QUEUE_AND_PARTIAL_FILL_NOT_OBSERVED",
                "SYNTHETIC_WEEKDAYS_NOT_AUTHENTICATED_TRADING_CALENDAR",
                "NO_REAL_ORDER_SUBMISSION_OR_OOS_STRATEGY_RETURNS",
                "FRIDAY_CLOSE_SNAPSHOT_IS_SYNTHETIC_NOT_EXCHANGE_PROOF",
                "OPEN_OR_PARTIAL_FRIDAY_SELL_DOES_NOT_CURE_CARRY_RISK",
            ])
    except (TypeError,KeyError,InvalidOperation,ValueError,OverflowError):
        return fail("MALFORMED_SYNTHETIC_FIXTURE_OR_PRICE")


def contract_summary():
    """Safe CI proof that a synthetic kernel cannot authorize any real trade."""
    return {
        "phase":PHASE,"status":"SYNTHETIC_KERNEL_AVAILABLE_RESEARCH_ONLY",
        "provenance":PROVENANCE,
        "execution_inputs":"SYNTHETIC_ONLY_NOT_FROM_VENDOR_OHLC",
        "verified_broker_fills":0,
        "historical_exchange_calendar_authenticated":False,
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "frozen_strategy_ready":False,
        "real_friday_liquidation_certified":False,
        "friday_session_close_proof_required_in_future_executable_gate":True,
        "trade_authorized":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }
