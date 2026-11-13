"""Offline MA20 holdout replay. Vendor observations are not fills or PIT proof."""
import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from collections import Counter, deque
from datetime import date
from decimal import Decimal
from pathlib import Path

from collector.p2_independent_bars import assess

HORIZONS = (3, 4, 5)  # Observed rows after the hypothetical entry row.
EPOCH = re.compile(r"[0-9a-f]{16}")
ISSUER = re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}")


def canonical_day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("noncanonical date")
    return parsed


def signal_indices(rows, train_end, through):
    """Consume a prefix of validated rows. Never access future OHLC or status."""
    window = deque(maxlen=20)
    running_sum = Decimal(0)
    previous_above = None
    for index, row in enumerate(rows):
        day = canonical_day(row["date"])
        if day > through:
            break
        if row["tradestatus"] != "1":
            previous_above = None
            continue
        close = Decimal(row["close"])
        if len(window) == 20:
            running_sum -= window[0]
        window.append(close)
        running_sum += close
        if len(window) != 20:
            continue
        above = close * 20 > running_sum
        if day > train_end and above and previous_above is False:
            yield index
        previous_above = above


def observe_outcome(rows, index, horizon, end):
    """Later rows describe evidence availability, never whether a signal existed."""
    following = []
    for row in rows[index + 1:index + horizon + 2]:
        if canonical_day(row["date"]) > end:
            break
        following.append(row)
    if any(row["tradestatus"] != "1" for row in following):
        return "VENDOR_SUSPENSION_OBSERVED"
    if len(following) != horizon + 1:
        return "RIGHT_CENSORED"
    return "VENDOR_ROWS_OBSERVED_NOT_FILL"


def replay_issuer(rows, train_end, validation_start, validation_end):
    # Compare the pre-specified midpoint's true truncated input with the same
    # prefix of the complete holdout run. Future status may change a label only.
    midpoint = validation_start + (validation_end - validation_start) // 2
    full = [i for i in signal_indices(rows, train_end, validation_end)
            if canonical_day(rows[i]["date"]) >= validation_start]
    prefix = [r for r in rows if canonical_day(r["date"]) <= midpoint]
    truncated = [i for i in signal_indices(prefix, train_end, midpoint)
                 if canonical_day(prefix[i]["date"]) >= validation_start]
    if truncated != [i for i in full if canonical_day(rows[i]["date"]) <= midpoint]:
        raise ValueError("future rows altered a prior signal")
    return [
        {
            "signal_after_close": rows[i]["date"],
            "forward_availability": {
                str(h): observe_outcome(rows, i, h, validation_end) for h in HORIZONS
            },
        }
        for i in full
    ]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def audit(root, archive_commit, epoch, train_end, validation_start, validation_end):
    root = Path(root).resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", archive_commit) or not EPOCH.fullmatch(epoch):
        raise ValueError("expected full archive commit and canonical epoch")
    if (Path(git(root, "rev-parse", "--show-toplevel")) != root
        or git(root, "rev-parse", "HEAD") != archive_commit
        or git(root, "status", "--porcelain", "--untracked-files=all", "--ignored")):
        raise ValueError("archive must be an unchanged checkout of the pinned commit")
    train, start, end = map(canonical_day, (train_end, validation_start, validation_end))
    if not train < start < end:
        raise ValueError("training and validation windows must be strictly ordered")
    receipts = sorted((root / epoch).glob("shard_*/quality.json"))
    if not receipts:
        raise ValueError("no archive receipts for requested epoch")
    seen = set()
    events = []
    for receipt in receipts:
        checked = assess(receipt.parent)
        for item in checked["details"]:
            code = item["code"]
            if not ISSUER.fullmatch(code) or code in seen:
                raise ValueError("unexpected or duplicate issuer within archive epoch")
            seen.add(code)
            raw = (receipt.parent / (code.replace(".", "_") + ".csv")).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            for event in replay_issuer(rows, train, start, end):
                events.append(dict(event, issuer=code, source_csv_sha256=digest))
    if not seen:
        raise ValueError("archive epoch has no checked issuers")
    events.sort(key=lambda e: (e["signal_after_close"], e["issuer"]))
    midpoint = (start + (end - start) // 2).isoformat()
    counts = {str(h): dict(Counter(e["forward_availability"][str(h)] for e in events))
              for h in HORIZONS}
    return {
        "phase": "P4_ASOF_CHRONOLOGICAL_RESEARCH_REPLAY",
        "status": ("VENDOR_REPLAY_NOT_CERTIFIED_OOS" if events else "NO_HOLDOUT_EVENTS"),
        "archive_commit_sha": archive_commit,
        "epoch": epoch,
        "train_end": train_end,
        "validation_start": validation_start,
        "validation_end": validation_end,
        "checked_issuers": len(seen),
        "holdout_signal_count": len(events),
        "holdout_signal_issuers": len({e["issuer"] for e in events}),
        "prefix_check_through": midpoint,
        "holdout_events_compared_in_prefix": sum(e["signal_after_close"] <= midpoint for e in events),
        "holdout_events_after_prefix": sum(e["signal_after_close"] > midpoint for e in events),
        "issuer_prefix_checks_passed": len(seen),
        "forward_availability_counts": counts,
        "events": events,
        "historical_PIT_verified": False,
        "historical_OOS_validated": False,
        "official_sessions_verified": False,
        "broker_fills_verified": 0,
        "trade_returns_computed": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("root", "archive-commit", "epoch", "train-end",
                "validation-start", "validation-end", "out"):
        parser.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    output = Path(args.out).resolve()
    if output.is_relative_to(Path(args.root).resolve()):
        parser.error("report path must not be inside the source archive")
    report = audit(args.root, args.archive_commit, args.epoch, args.train_end,
                   args.validation_start, args.validation_end)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "events"}, sort_keys=True))


if __name__ == "__main__":
    main()
