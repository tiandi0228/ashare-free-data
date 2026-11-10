"""Offline point-in-time prediction audit; never infer one-word limit-up from daily OHLC.

A forecast is a dated hypothesis, not a verified claim about future prices.
Even identical daily OHLC and asserted limit prices cannot prove continuous
limit-up transactions or authenticated exchange trading/auction records.
"""
import argparse
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from collector.p4_dual_horizon_research import MAINBOARD

PHASE = "P4_ONE_WORD_LIMITUP_PREDICTION_REPLAY_NO_TRADES"
SHA = re.compile(r"[0-9a-f]{64}\Z")
RULE = "OPEN_AT_LIMIT_AND_ALL_EXECUTED_TRADES_AT_LIMIT_UNTIL_CLOSE"


def _date(text):
    if not isinstance(text, str):
        raise ValueError("date is required")
    d = date.fromisoformat(text)
    if d.isoformat() != text:
        raise ValueError("noncanonical date")
    return d


def _price(value):
    if not isinstance(value, str):
        raise ValueError("price must be a string decimal")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid decimal price") from None
    if not number.is_finite() or number <= 0:
        raise ValueError("positive finite price required")
    if number.as_tuple().exponent < -2:
        raise ValueError("price must use valid cent tick precision")
    return number


def assess(packet):
    if not isinstance(packet, dict):
        raise ValueError("prediction and optional outcome packet required")
    issued = _date(packet.get("predicted_on"))
    target = _date(packet.get("session_on"))
    if target <= issued:
        raise ValueError("forecast must precede target session date")
    code = packet.get("issuer")
    if not isinstance(code, str) or not MAINBOARD.fullmatch(code):
        raise ValueError("nonmainboard or invalid issuer")
    if packet.get("prediction") != "ONE_WORD_LIMIT_UP":
        raise ValueError("unsupported prediction taxonomy")
    if packet.get("prediction_rule") != RULE:
        raise ValueError("prediction must freeze one-word limit-up test")
    if packet.get("trade_gate") != "BLOCKED" or packet.get("orders") != []:
        raise ValueError("forecast may not include executable order")
    evidence = packet.get("observation")
    result = "UNRESOLVED_NO_INDEPENDENT_SESSION_EVIDENCE"
    reasons = ["PREDICTION_NOT_AUTHENTICATED_AS_PRE_EVENT_TIMESTAMP",
               "EXCHANGE_SESSION_AND_LIMIT_RULE_NOT_AUTHENTICATED"]
    observables = None
    if evidence is not None:
        if not isinstance(evidence, dict):
            raise ValueError("malformed observed session")
        if _date(evidence.get("session_on")) != target:
            raise ValueError("observation target day mismatch")
        sha = evidence.get("source_sha256")
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError("price source digest must be pinned")
        if not isinstance(evidence.get("source_ref"), str) or not evidence["source_ref"].startswith("https://") or len(evidence["source_ref"]) > 512:
            raise ValueError("price source reference missing")
        prev = _price(evidence.get("previous_close"))
        op = _price(evidence.get("open"))
        hi = _price(evidence.get("high"))
        lo = _price(evidence.get("low"))
        close = _price(evidence.get("close"))
        ceiling = _price(evidence.get("exchange_limit_up_price"))
        if not (lo <= op <= hi and lo <= close <= hi and ceiling >= prev):
            raise ValueError("inconsistent session OHLC or limit")
        if type(evidence.get("complete_session")) is not bool:
            raise ValueError("explicit complete-session flag required")
        if type(evidence.get("original_exchange_ticks_authenticated")) is not bool:
            raise ValueError("explicit tick authentication status required")
        if type(evidence.get("official_limit_price_authenticated")) is not bool:
            raise ValueError("explicit limit authenticity required")
        # OHLC disproves an all-day limit-up when an executed open, low or
        # close is below ceiling. An OHLC match alone CANNOT prove the path.
        below = op < ceiling or lo < ceiling or close < ceiling
        above = hi > ceiling or op > ceiling or close > ceiling
        if above:
            raise ValueError("claimed exchange daily maximum breached")
        observables = {"observed_open": str(op), "observed_low": str(lo),
                       "observed_high": str(hi), "observed_close": str(close),
                       "claimed_limit_up": str(ceiling),
                       "daily_ohlc_matches_one_word_pattern": all(
                           x == ceiling for x in (op, hi, lo, close)),
                       "source_document_sha_pinned_not_replayed": True}
        if evidence["complete_session"] and below:
            result = "FALSIFIED_BY_DAILY_COMPLETED_OHLC_CLAIM"
            reasons.append("DAILY_OPEN_LOW_OR_CLOSE_BELOW_CLAIMED_LIMIT")
        elif evidence["complete_session"] and all(x == ceiling for x in (op, hi, lo, close)):
            result = "DAILY_OHLC_COMPATIBLE_NOT_CERTIFIED_ONE_WORD"
            reasons.append("DAILY_OHLC_CANNOT_CERTIFY_ALL_TRANSACTIONS")
        else:
            result = "UNRESOLVED_PARTIAL_SESSION_OBSERVATION"
            reasons.append("SESSION_NOT_COMPLETE_OR_PRICE_PATTERN_INCONCLUSIVE")
        if not evidence["original_exchange_ticks_authenticated"]:
            reasons.append("FULL_EXCHANGE_TICK_REPLAY_NOT_VERIFIED")
        if not evidence["official_limit_price_authenticated"]:
            reasons.append("SECURITY_SPECIFIC_EXCHANGE_LIMIT_NOT_VERIFIED")
    return {
        "phase": PHASE, "issuer": code, "predicted_on": issued.isoformat(),
        "session_on": target.isoformat(), "prediction": packet["prediction"],
        "prediction_rule": RULE, "audit_state": result,
        "observation": observables, "limitations": reasons,
        "official_limit_price_verified_by_this_module": False,
        "actual_one_word_limit_up_certified": False,
        "forecast_accuracy_claimed": False,
        "prediction_observation_independently_replayed": False,
        "buy_recommendations_authorized": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = assess(json.loads(args.packet.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": PHASE, "audit_state": result["audit_state"],
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
