"""Read-only, fail-closed event-driven A-share research, never a trade signal.

A public schedule is known in advance, and even verified venue exposure does not
prove incremental earnings, price continuation, or a tradeable opening print.
This gate does not fetch or authenticate documents; claims stay unverified.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

from collector.p4_dual_horizon_research import MAINBOARD

SHA = re.compile(r"[a-f0-9]{64}\Z")
EXPOSURES = {"venue_named", "signed_contract", "location_only", "no_evidence"}
PHASE = "P4_EVENT_DRIVEN_EXPOSURE_RESEARCH_ONLY"


def _day(value):
    if not isinstance(value, str):
        raise ValueError("date required")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("noncanonical date")
    return parsed


def assess(packet):
    if not isinstance(packet, dict) or type(packet.get("issuers")) is not list:
        raise ValueError("event research packet required")
    asof = _day(packet.get("asof"))
    event = packet.get("event")
    if not isinstance(event, dict):
        raise ValueError("event metadata required")
    published = _day(event.get("schedule_published_on"))
    event_day = _day(event.get("event_on"))
    if published > asof or event_day < published:
        raise ValueError("event chronology invalid")
    if not isinstance(event.get("name"), str) or not 1 <= len(event["name"]) <= 200:
        raise ValueError("bounded event name required")
    event_url = event.get("schedule_source")
    if not isinstance(event_url, str) or not event_url.startswith("https://") or len(event_url) > 512:
        raise ValueError("schedule source reference required")
    if type(event.get("source_authenticated")) is not bool:
        raise ValueError("explicit schedule authenticity status required")
    rows = packet["issuers"]
    if len(rows) > 50:
        raise ValueError("bounded candidate research only")
    seen = set()
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed candidate")
        code = row.get("issuer")
        if not isinstance(code, str) or not MAINBOARD.fullmatch(code) or code in seen:
            raise ValueError("duplicate or out-of-mainboard issuer")
        seen.add(code)
        exposure = row.get("exposure")
        if exposure not in EXPOSURES:
            raise ValueError("unknown exposure class")
        source = row.get("company_source")
        sha = row.get("company_excerpt_sha256")
        disclosed = row.get("company_disclosed_on")
        if exposure in ("venue_named", "signed_contract"):
            if (not isinstance(source, str) or not source.startswith("https://")
                or len(source) > 512 or not isinstance(sha, str)
                or not SHA.fullmatch(sha) or _day(disclosed) > asof):
                raise ValueError("business exposure provenance missing")
        elif any(row.get(k) is not None for k in ("company_source", "company_excerpt_sha256", "company_disclosed_on")):
            raise ValueError("location-only exposure cannot claim company-specific evidence")
        if type(row.get("official_pit_non_st_halt_verified")) is not bool:
            raise ValueError("explicit PIT status required")
        # Unknown and positive assertions are both non-executable without
        # independent originals, fresh prices, pre-frozen exit and fee math.
        reasons = ["NO_INDEPENDENT_COMPANY_SOURCE_REPLAY",
                   "NO_RECONCILED_CURRENT_EXECUTABLE_QUOTES",
                   "NO_SECTOR_CROSS_CONFIRMATION",
                   "NO_FEE_INCLUSIVE_RISK_REWARD_AND_T_PLUS_ONE_GATE"]
        if not event["source_authenticated"]:
            reasons.append("OFFICIAL_EVENT_SCHEDULE_NOT_AUTHENTICATED")
        if not row["official_pit_non_st_halt_verified"]:
            reasons.append("OFFICIAL_PIT_UNIVERSE_STATUS_NOT_CERTIFIED")
        if exposure == "location_only":
            reasons.append("LOCATION_IS_NOT_BUSINESS_EXPOSURE")
        if exposure == "no_evidence":
            reasons.append("NO_EVENT_RELATION_EVIDENCE")
        if event_day > asof:
            reasons.append("FUTURE_EVENT_NOT_A_CONFIRMED_MARKET_REACTION")
        out.append({
            "issuer": code, "declared_exposure": exposure,
            "relationship_source_ref": source if exposure in ("venue_named", "signed_contract") else None,
            "exposure_category": ("BUSINESS_LINK_ASSERTED_UNVERIFIED" if exposure in ("venue_named", "signed_contract")
                                  else "GEOGRAPHIC_THEME_ONLY" if exposure == "location_only"
                                  else "NO_SUPPORTED_LINK"),
            "short_3_to_5_sessions": "WATCH_RESEARCH_ONLY",
            "medium_1_to_3_months": "INDEPENDENT_FUNDAMENTALS_REQUIRED",
            "one_word_limit_up_predicted": False,
            "price_direction_verified": False,
            "buy_allowed": False, "blockers": reasons,
        })
    return {"phase": PHASE, "asof": asof.isoformat(),
            "event_name": event["name"], "event_on": event_day.isoformat(),
            "schedule_public_before_asof": published <= asof,
            "schedule_is_not_a_surprise_catalyst": published < asof,
            "independent_external_source_replay_completed": False,
            "scoped_issuers": len(out), "symbols": out,
            "full_market_screen_performed": False,
            "one_word_limit_up_can_be_predicted": False,
            "buy_recommendations_authorized": False,
            "trade_gate": "BLOCKED", "orders": [],
            "executable_candidates": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = assess(json.loads(args.packet.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": result["phase"], "scoped_issuers": result["scoped_issuers"],
                      "trade_gate": result["trade_gate"]}))


if __name__ == "__main__":
    main()
