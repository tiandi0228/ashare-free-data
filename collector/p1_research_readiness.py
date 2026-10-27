"""Read-only research readiness status; this module never opens the trade gate."""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import validate


def assess(ledger):
    validate(ledger)
    missing = []
    if ledger["completed_shards"] != ledger["shard_count"]:
        missing.append("HISTORICAL_VENDOR_SHARDS_INCOMPLETE")
    if ledger.get("full_market_bars_certified") is not True:
        missing.append("FULL_MARKET_BARS_NOT_CERTIFIED")
    if ledger.get("historical_PIT_verified") is not True:
        missing.append("HISTORICAL_PIT_NOT_AUTHENTICATED")
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
        "trade_gate": "BLOCKED",
        "buy_recommendations_authorized": False,
        "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = assess(json.loads(Path(args.ledger).read_text()))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
