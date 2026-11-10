"""Validate provenance-bearing dual-horizon evidence without inventing facts.

A SHA over locally supplied excerpt bytes detects accidental mutation, NOT
whether a URL is real, a source is official, or an asserted conclusion follows
from its excerpt. Therefore all assessments stay UNVERIFIED and NON-ACTIONABLE.
"""
import argparse
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from collector.p4_dual_horizon_research import assess, SHORT, MEDIUM, MAINBOARD

SHA = re.compile(r"[a-f0-9]{64}\Z")
FIELDS = {
    "short": set(SHORT) | {"net_risk_reward_ratio",
                           "planned_net_portfolio_loss_fraction"},
    "medium": set(MEDIUM) | {"stress_drawdown_fraction",
                              "debt_and_liquidity_risk_reviewed",
                              "earnings_event_risk_reviewed",
                              "fundamental_invalidation_defined"},
    "universe": {"official_pit_mainboard_non_st_confirmed",
                 "no_suspension_confirmed"},
}
NUMBERS = {"net_risk_reward_ratio", "planned_net_portfolio_loss_fraction",
           "stress_drawdown_fraction"}
SOURCE_TYPES = {"exchange_disclosure", "exchange_security_status",
                "financial_report", "licensed_price_feed", "vendor_bar",
                "valuation_research", "sector_publication"}
MAX_RECORDS_PER_SYMBOL = 40
MAX_SYMBOLS = 50


def _day(text):
    if not isinstance(text, str):
        raise ValueError("missing date")
    value = date.fromisoformat(text)
    if value.isoformat() != text:
        raise ValueError("noncanonical date")
    return value


def _validate_value(name, value):
    if name in NUMBERS:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError("invalid numeric research assertion")
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("invalid numeric research assertion") from None
        if not number.is_finite() or number < 0:
            raise ValueError("nonfinite or negative research assertion")
        return str(number)
    if type(value) is not bool:
        raise ValueError("explicit true/false evidence assertion required")
    return value


def _check_record(record, asof):
    if not isinstance(record, dict):
        raise ValueError("malformed evidence receipt")
    scope = record.get("scope")
    name = record.get("indicator")
    if scope not in FIELDS or not isinstance(name, str) or name not in FIELDS[scope]:
        raise ValueError("unknown or cross-horizon evidence indicator")
    source_type = record.get("source_type")
    if source_type not in SOURCE_TYPES:
        raise ValueError("unknown evidence source type")
    if scope == "universe" and source_type != "exchange_security_status":
        raise ValueError("official point-in-time universe needs security-status evidence")
    ref = record.get("source_ref")
    excerpt = record.get("source_excerpt")
    expected = record.get("source_excerpt_sha256")
    if (not isinstance(ref, str) or not ref.startswith(("https://", "http://"))
        or len(ref) > 512 or not isinstance(excerpt, str)
        or not 1 <= len(excerpt) <= 4096
        or not isinstance(expected, str) or not SHA.fullmatch(expected)):
        raise ValueError("missing immutable receipt provenance")
    actual = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    if expected != actual:
        raise ValueError("source excerpt SHA mismatch")
    published = _day(record.get("published_on"))
    if published > asof:
        raise ValueError("future evidence cannot support as-of research")
    # Conservative age boundaries, not proof of market recency.
    age = (asof - published).days
    max_age = 7 if scope == "short" else 120 if scope == "medium" else 7
    if age > max_age:
        raise ValueError("stale evidence cannot support this horizon")
    return scope, name, _validate_value(name, record.get("value")), published


def inspect(packet):
    if not isinstance(packet, dict) or type(packet.get("symbols")) is not list:
        raise ValueError("structured evidence packet required")
    asof = _day(packet.get("asof"))
    if len(packet["symbols"]) > MAX_SYMBOLS:
        raise ValueError("unbounded evidence universe")
    symbols = []
    seen = set()
    receipts_count = 0
    for item in packet["symbols"]:
        if not isinstance(item, dict):
            raise ValueError("invalid symbol evidence packet")
        issuer = item.get("issuer")
        if not isinstance(issuer, str) or not MAINBOARD.fullmatch(issuer) or issuer in seen:
            raise ValueError("unknown, non-mainboard or duplicate issuer")
        seen.add(issuer)
        records = item.get("receipts")
        if not isinstance(records, list) or len(records) > MAX_RECORDS_PER_SYMBOL:
            raise ValueError("bounded evidence receipt list required")
        claims = {"short": {}, "medium": {}, "universe": {}}
        latest = {"short": None, "medium": None, "universe": None}
        for row in records:
            scope, name, value, published = _check_record(row, asof)
            if name in claims[scope]:
                raise ValueError("conflicting or duplicated evidence assertion")
            claims[scope][name] = value
            latest[scope] = max(latest[scope], published) if latest[scope] else published
            receipts_count += 1
        # Source identities bind to the local packet, but do NOT authenticate
        # the excerpt origin or substantiate the semantic assertion.
        source_digest = hashlib.sha256(json.dumps(
            records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")).hexdigest()
        def lane(scope):
            if not claims[scope]:
                return None
            return {
                **claims[scope],
                "source": "UNAUTHENTICATED_RECEIPT_PACKET_SHA256:" + source_digest,
                "published_on": latest[scope].isoformat(),
            }
        symbols.append({
            "issuer": issuer, "short": lane("short"), "medium": lane("medium"),
            "universe_guard": {
                **claims["universe"],
                "source": ("UNAUTHENTICATED_RECEIPT_PACKET_SHA256:" + source_digest
                           if claims["universe"] else ""),
                "published_on": (latest["universe"].isoformat()
                                 if latest["universe"] else None),
            },
        })
    provisional = assess({"asof": asof.isoformat(), "symbols": symbols})
    return {
        "phase": "P4_DUAL_HORIZON_RECEIPT_PROVENANCE_GATE",
        "status": "LOCAL_RECEIPT_INTEGRITY_ONLY_SOURCE_AUTHENTICITY_UNVERIFIED",
        "asof": asof.isoformat(),
        "receipts_sha_checked": receipts_count,
        "evaluated_symbols": len(symbols),
        "provisional_assertion_only_assessment": provisional,
        "source_authenticity_verified": False,
        "semantic_claims_independently_verified": False,
        "official_pit_universe_certified": False,
        "live_quote_verified": False,
        "eligible_buy_candidates": [],
        "buy_recommendations_authorized": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(json.loads(args.packet.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": result["phase"],
                      "receipts_sha_checked": result["receipts_sha_checked"],
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
