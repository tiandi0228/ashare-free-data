"""Read-only frozen P1 roster age evidence: never equate history with live picks."""
import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from collector.p1_roster_lock import unpack

BEIJING = ZoneInfo("Asia/Shanghai")


def inspect(lock, observed_at):
    if not isinstance(observed_at, dt.datetime) or observed_at.tzinfo is None:
        raise ValueError("timezone-aware audit time required")
    # Independently validate pinned original CSV and receipt SHA, not only date.
    _, receipt = unpack(lock)
    try:
        source_day = dt.date.fromisoformat(receipt["requested_day"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid original source date") from exc
    current = observed_at.astimezone(BEIJING).date()
    age = (current - source_day).days
    if age < 0:
        raise ValueError("future vendor source day")
    return {
        "phase": "P1_FROZEN_ROSTER_AGE_RESEARCH_ONLY",
        "source_sha256": lock["source_sha256"],
        "source_requested_day": source_day.isoformat(),
        "audited_beijing_day": current.isoformat(),
        "source_age_calendar_days": age,
        "research_snapshot_frozen": True,
        "current_day_roster_authenticated": False,
        "roster_freshness_status": (
            "HISTORICAL_FROZEN_SNAPSHOT_NOT_CURRENT"
            if age else "SAME_DAY_UNVERIFIED_NOT_LIVE_AUTHENTICATED"
        ),
        "historical_PIT_verified": False,
        "publisher_authenticated": False,
        "buy_recommendations_authorized": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = inspect(json.loads(args.lock.read_text(encoding="utf-8")),
                     dt.datetime.now(dt.timezone.utc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
