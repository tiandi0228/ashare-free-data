"""Fail-closed research audit of cancel-and-replace limit orders; no real orders."""
from collector.p4_limit_order_replay import replay,parse_time

def review(*,original,replacement):
    first=replay(**original)
    second=replay(**replacement)
    if original["side"]!=replacement["side"]:raise ValueError("replacement side mismatch")
    if not first["cancel_receipt_present"]:raise ValueError("cancel acknowledgement missing")
    cancels=[e for e in original["events"] if e["kind"]=="CANCEL_RECEIPT"]
    if len(cancels)!=1:raise ValueError("exactly one cancellation required")
    cancellation=parse_time(cancels[0]["observed_at"])
    if parse_time(replacement["placed_at"])<=cancellation:raise ValueError("replacement starts before acknowledged cancel")
    remaining=original["order_shares"]-first["receipt_fill_shares"]
    if replacement["order_shares"]>remaining:raise ValueError("replacement overcommits cancelled remainder")
    if first["receipt_fill_shares"]+second["receipt_fill_shares"]>original["order_shares"]:
        raise ValueError("aggregate fill over original quantity")
    return {"phase":"P4_V22_CANCEL_REPLACE_RESEARCH_AUDIT",
            "original_requested_shares":original["order_shares"],
            "original_receipt_fill_shares":first["receipt_fill_shares"],
            "cancelled_remainder_shares":remaining,
            "replacement_requested_shares":replacement["order_shares"],
            "replacement_receipt_fill_shares":second["receipt_fill_shares"],
            "aggregate_receipt_fill_shares":first["receipt_fill_shares"]+second["receipt_fill_shares"],
            "unfilled_original_capacity":original["order_shares"]-first["receipt_fill_shares"]-second["receipt_fill_shares"],
            "independent_execution_verified":False,
            "historical_OOS_validated":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
