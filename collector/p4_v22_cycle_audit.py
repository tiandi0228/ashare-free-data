"""Cross-module V2.2 evidence-only position lifecycle audit.

All order receipts and assertions here are research inputs, NOT authenticated
broker fills or official historical trading permissions. Never emit orders,
verified PnL or executable candidates.
"""
from datetime import date
from decimal import Decimal
from collector.p4_limit_order_replay import replay as replay_order
from collector.p4_partial_fill_fee_inventory import summarize
from collector.p4_unified_execution_preflight import assess as preflight_check
from collector.p4_time_exit_unresolved import assess as time_exit_check
from collector.p4_execution_arithmetic import replay as scenario_replay


def _fill_days(order):
    return {date.fromisoformat(e["observed_at"][:10])
            for e in order["events"] if e["kind"] == "FILL_RECEIPT"}


def audit(*, issuer, buy_order, sell_order, asof_day, calendar_sessions,
          exit_market_inputs, planned_stop_price, sell_slippage="0"):
    today = date.fromisoformat(asof_day)
    if not isinstance(calendar_sessions, list) or len(set(calendar_sessions)) != len(calendar_sessions):
        raise ValueError("missing or duplicated session calendar")
    sessions = [date.fromisoformat(x) for x in calendar_sessions]
    if sessions != sorted(sessions) or today not in sessions:
        raise ValueError("observation day not in ordered calendar")
    buy = replay_order(**buy_order)
    if buy["side"] != "BUY":
        raise ValueError("buy leg required")
    if any(date.fromisoformat(e["observed_at"][:10]) > today for e in buy_order["events"]):
        raise ValueError("future buy evidence")
    buy_days = _fill_days(buy_order)
    if len(buy_days) > 1:
        raise ValueError("multi-day entry requires separately frozen T+1 exit rules")
    if not buy_days:
        if sell_order is not None:
            raise ValueError("cannot sell unfilled buy")
        return {"phase": "P4_V22_END_TO_END_RESEARCH_AUDIT",
                "position_state": "UNFILLED_ENTRY_EXCLUDED_FROM_RETURNS",
                "observed_buy_shares": 0, "observed_sell_shares": 0,
                "modeled_net_pnl_finalized": False, "fill_certified": False,
                "historical_OOS_validated": False,
                "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}

    entry_day = next(iter(buy_days)).isoformat()
    if date.fromisoformat(entry_day) not in sessions or today <= date.fromisoformat(entry_day):
        raise ValueError("T+1 observation required")
    if not isinstance(exit_market_inputs, dict):
        raise ValueError("explicit exit market evidence required")
    fixed = {"issuer": issuer, "entry_day": entry_day, "exit_day": asof_day,
             "calendar_sessions": calendar_sessions, "side": "SELL"}
    for k, v in fixed.items():
        if k in exit_market_inputs and exit_market_inputs[k] != v:
            raise ValueError("exit market input conflicts with entry, date or side")
    preflight = preflight_check(**{**exit_market_inputs, **fixed})
    if sell_order is not None:
        if any(date.fromisoformat(e["observed_at"][:10]) > today for e in sell_order["events"]):
            raise ValueError("future sell evidence")
        if _fill_days(sell_order) - {today}:
            raise ValueError("multi-date exit needs per-session market evidence")
    inventory = summarize(buy_order=buy_order, sell_order=sell_order)
    observed_sell = inventory["observed_sell_shares"]
    time_check = time_exit_check(entry_day=entry_day, observation_day=asof_day,
                                calendar_sessions=calendar_sessions, preflight=preflight,
                                receipt_verified=observed_sell > 0)
    weighted = buy["weighted_fill_price"]
    if weighted is None:
        raise ValueError("missing observed buy price")
    stop = Decimal(str(planned_stop_price))
    buy_price = Decimal(weighted)
    if not stop.is_finite() or stop <= 0 or stop >= buy_price:
        raise ValueError("stop must be finite, positive and below observed buy")
    hypothetical = scenario_replay(
        buy_price=str(buy_price), sell_price=str(stop),
        shares=buy["receipt_fill_shares"], buy_day=entry_day,
        sell_day=asof_day, planned_stop_price=str(stop),
        slippage_sell=sell_slippage)
    stop_risk = hypothetical["planned_stop_risk_scenario"]
    conflict = observed_sell > 0 and not preflight["candidate_for_independent_receipt_replay"]
    state = time_check["state"]
    if conflict:
        state = "SELL_RECEIPT_CONFLICTS_WITH_UNCERTIFIED_MARKET_STATE"
    elif observed_sell and inventory["inventory_shares"] > 0:
        state = "PARTIAL_EXIT_REMAINDER_UNRESOLVED"
    return {"phase": "P4_V22_END_TO_END_RESEARCH_AUDIT",
            "issuer": issuer, "entry_day": entry_day, "asof_day": asof_day,
            "position_state": state, "sessions_elapsed": time_check["sessions_elapsed"],
            "observed_buy_shares": inventory["observed_buy_shares"],
            "observed_sell_shares": observed_sell,
            "remaining_shares": inventory["inventory_shares"],
            "modeled_buy_fees": inventory["buy_fees_model"],
            "modeled_sell_fees": inventory["sell_fees_model"],
            "planned_stop_loss_including_fees": stop_risk["scenario_net_loss"],
            "planned_stop_within_3pct_budget": stop_risk["scenario_within_budget"],
            "stop_gap_limit_risk_covered": False,
            "receipt_conflicts_with_market_preflight": conflict,
            "model_assumptions_not_independent_receipts": True,
            "modeled_net_pnl_finalized": False, "fill_certified": False,
            "historical_OOS_validated": False,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}
