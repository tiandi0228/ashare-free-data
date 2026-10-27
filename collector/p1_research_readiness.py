"""Read-only research readiness status; this module never opens the trade gate."""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import validate


def assess(ledger, archive_audit=None):
    validate(ledger)
    missing = []
    if ledger["completed_shards"] != ledger["shard_count"]:
        missing.append("HISTORICAL_VENDOR_SHARDS_INCOMPLETE")
    if ledger.get("full_market_bars_certified") is not True:
        missing.append("FULL_MARKET_BARS_NOT_CERTIFIED")
    if ledger.get("historical_PIT_verified") is not True:
        missing.append("HISTORICAL_PIT_NOT_AUTHENTICATED")
    if archive_audit is None:
        missing.append("CSV_ARCHIVE_AUDIT_UNAVAILABLE")
    elif (not isinstance(archive_audit,dict) or
          archive_audit.get("trade_gate")!="BLOCKED" or
          archive_audit.get("archive_complete") is not True or
          type(archive_audit.get("archived_issuers")) is not int or
          archive_audit["archived_issuers"]!=ledger["completed_issuers"] or
          archive_audit.get("archive_gap_issuers")!=0):
        missing.append("CSV_ARCHIVE_NOT_CERTIFIED")
    # None of these real-time execution checks can be certified from a vendor
    # history ledger. They require independently timestamped market evidence.
    missing.extend([
        "REALTIME_QUOTE_FRESHNESS_NOT_VERIFIED",
        "COMPLETE_ONE_MINUTE_BAR_NOT_VERIFIED",
        "POINT_IN_TIME_SECURITY_UNIVERSE_NOT_VERIFIED",
        "TRADE_COST_AND_EXECUTION_RULES_NOT_VERIFIED",
    ])
    # The ledger is intentionally research-only. A complete vendor collection
    # is not permission to route any order or advertise executable picks.
    return {
        "phase": "P1_RESEARCH_READINESS",
        "source_sha256": ledger["source_sha256"],
        "completed_shards": ledger["completed_shards"],
        "shard_count": ledger["shard_count"],
        "completed_issuers": ledger["completed_issuers"],
        "unresolved_checks": missing,
        "research_data_complete": ledger["completed_shards"] == ledger["shard_count"],
        "realtime_execution_checks_verified": False,
        "trade_gate": "BLOCKED",
        "buy_recommendations_authorized": False,
        "orders": [],
        "executable_candidates": [],
    }


def assess_or_block(ledger, archive_audit=None):
    """Never publish an actionable report for malformed upstream evidence."""
    try:
        return assess(ledger, archive_audit)
    except (ValueError, KeyError, TypeError, AttributeError):
        return unavailable("CURRENT_LEDGER_INVALID")


def unavailable(reason="CURRENT_LEDGER_UNAVAILABLE"):
    """Explicit fail-closed report when an upstream job produced no ledger."""
    return {
        "phase": "P1_RESEARCH_READINESS",
        "source_sha256": None,
        "completed_shards": None,
        "shard_count": None,
        "completed_issuers": None,
        "unresolved_checks": [reason],
        "research_data_complete": False,
        "realtime_execution_checks_verified": False,
        "trade_gate": "BLOCKED",
        "buy_recommendations_authorized": False,
        "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger")
    parser.add_argument("--archive-audit")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.ledger:
        try:
            report = assess_or_block(json.loads(Path(args.ledger).read_text()),\n                json.loads(Path(args.archive_audit).read_text()) if args.archive_audit else None)
        except (OSError, UnicodeError, json.JSONDecodeError):
            report = unavailable("CURRENT_LEDGER_INVALID")
    else:
        report = unavailable()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
