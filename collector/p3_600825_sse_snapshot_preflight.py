"""Screen a normalized IS120 0.62 M102 excerpt. Never authenticate its provenance."""
import argparse
from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
import re

BEIJING = timezone(timedelta(hours=8))
TARGET = "20260907"
CUTOFF = time(9, 15)
SPEC = "IS120_BINARY_0.62"

# These timestamps describe the exchange snapshot, not the recipient's receipt
# and not the public dissemination time of an issuer announcement.
def _clock(value, digits, pattern):
    if not isinstance(value, str) or not re.fullmatch(rf"[0-9]{{{digits}}}", value):
        raise ValueError("invalid clock field width")
    return datetime.strptime(value, pattern).replace(tzinfo=BEIJING)


def assess(row=None):
    result = {
        "issuer": "sh.600825",
        "trade_date": "2026-09-07",
        "status": "NO_HISTORICAL_SNAPSHOT_SUPPLIED",
        "exchange_sending_time_beijing": None,
        "last_update_time_beijing": None,
        "historical_snapshot_coverage_confirmed": False,
        "source_authenticated": False,
        "initial_halt_before_auction_verified": False,
        "official_first_release_verified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    if row is None:
        return result
    if not isinstance(row, dict):
        raise ValueError("snapshot excerpt must be a JSON object")
    expected = {
        "schema": SPEC, "venue": "SSE", "MsgType": "M102", "SecurityType": 1,
        "TradSesMode": 3, "TradeDate": TARGET, "MDStreamID": "MD002", "SecurityID": "600825",
    }
    if any(type(row.get(key)) is not type(value) or row[key] != value
           for key, value in expected.items()):
        raise ValueError("snapshot is outside the pinned security/date/feed scope")
    phase = row.get("TradingPhaseCode")
    if not isinstance(phase, str) or not re.fullmatch(r"[SCTEPMNU][01 ][01 ][01 ] {4}", phase):
        raise ValueError("invalid stock TradingPhaseCode")
    sent = _clock(row.get("SendingTime"), 17, "%Y%m%d%H%M%S%f")
    last_update = row.get("LastUpdateTime")
    if not isinstance(last_update, str):
        raise ValueError("LastUpdateTime must be a zero-padded string")
    updated = _clock(TARGET + last_update, 17, "%Y%m%d%H%M%S%f")
    if sent.strftime("%Y%m%d") != TARGET or updated > sent or updated.time() == time(0):
        raise ValueError("inconsistent exchange snapshot timestamps")
    if phase[0] == "P" and phase[1:3] != "01":
        raise ValueError("halt flags conflict or listed stock identity is unconfirmed")
    if phase[0] != "P":
        status = "NO_EXPLICIT_HALT_IN_THIS_ROW"
    elif sent.time() >= CUTOFF:
        status = "HALT_SENT_AT_OR_AFTER_AUCTION"
    else:
        status = "PRE_AUCTION_HALT_CANDIDATE_PROVENANCE_REQUIRED"
    return {**result, "status": status, "exchange_sending_time_beijing": sent.isoformat(),
            "last_update_time_beijing": updated.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excerpt", type=Path, help="Normalized JSON excerpt, not a raw exchange frame")
    args = parser.parse_args()
    if args.excerpt is None:
        result = assess()
    else:
        row = json.loads(args.excerpt.read_bytes())
        if not isinstance(row, dict):
            parser.error("snapshot excerpt must be a JSON object")
        result = assess(row)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
