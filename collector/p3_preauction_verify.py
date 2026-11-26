"""Recompute one trial from retained bytes without promoting research evidence."""
import argparse
import base64
import binascii
from datetime import date, datetime
import json
from pathlib import Path

from collector.p3_preauction_receipt import MAX_RAW, SHANGHAI, instant
from collector.p3_preauction_trial import ISSUERS, SLOTS
from collector.p3_sina_preauction_probe import build_result


def load(path, limit):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"oversized {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"invalid {path.name}")
    return value


def verify(root):
    summary = load(root / "summary.json", 32768)
    if (summary.get("schema") != "p3_preauction_trial_v1"
            or summary.get("trade_gate") != "BLOCKED"
            or summary.get("preauction_visibility_certified") is not False
            or summary.get("historical_PIT_verified") is not False
            or summary.get("orders") != [] or summary.get("executable_candidates") != []):
        raise ValueError("invalid diagnostic summary")
    day = date.fromisoformat(summary["date"])
    if day.weekday() >= 5:
        raise ValueError("invalid trial weekday")
    slots = [(name, issuer, start, end) for name, start, end in SLOTS for issuer in ISSUERS]
    records = summary["records"]
    if not isinstance(records, list) or len(records) != len(slots):
        raise ValueError("wrong slot count")
    count = checked = 0
    outputs = {"summary.json"}
    for item, (name, issuer, start, end) in zip(records, slots):
        if not isinstance(item, dict) or (item.get("slot"), item.get("issuer")) != (name, issuer):
            raise ValueError("wrong slot identity")
        label = item.get("result")
        if label in ("MISSED_SLOT", "SOURCE_ERROR"):
            if "file" in item:
                raise ValueError("unexpected response file on failed slot")
            continue
        fname = f"{name}_{issuer}.json"
        if item.get("file") != fname or (root / fname).is_symlink():
            raise ValueError("invalid response file")
        saved = load(root / fname, MAX_RAW * 2)
        raw = base64.b64decode(saved["raw_base64"], validate=True)
        rebuilt = build_result(raw, issuer, saved["captured_at"])
        if saved != rebuilt or any(item.get(key) != rebuilt[key] for key in
                                  ("timing", "raw_sha256", "captured_at", "source_time")):
            raise ValueError(f"response mismatch: {fname}")
        captured = instant(rebuilt["captured_at"]).astimezone(SHANGHAI)
        inside = datetime.combine(day, start, SHANGHAI) <= captured < datetime.combine(day, end, SHANGHAI)
        if label != ("CAPTURED" if inside else "OUTSIDE_SLOT"):
            raise ValueError(f"slot timing mismatch: {fname}")
        outputs.add(fname)
        checked += 1
        count += inside and name != "post_control" and rebuilt["timing"] == "SAME_DAY_CAPTURE_BEFORE_0915"
    if outputs != {file.name for file in root.glob("*.json")}:
        raise ValueError("unexpected or missing JSON output")
    total = summary.get("same_day_preauction_observations")
    if type(total) is not int or total != count:
        raise ValueError("pre-auction count mismatch")
    return dict(date=day.isoformat(), verified_receipts=checked, same_day_preauction_observations=count,
                capture_clock_attested=False, source_mapping_verified=False, historical_PIT_verified=False,
                preauction_visibility_certified=False, trade_gate="BLOCKED", orders=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trial_directory", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.trial_directory)
    except (OSError, ValueError, KeyError, TypeError, binascii.Error) as exc:
        parser.exit(1, f"Trial verification failed ({type(exc).__name__}): {exc}\n")
    print(json.dumps(result))
    return 0 if result["same_day_preauction_observations"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
