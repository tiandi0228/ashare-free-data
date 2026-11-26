"""Run a one-date, read-only Sina pre-auction trial on an already awake host."""
import argparse
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
from time import sleep

from collector.p3_preauction_receipt import SHANGHAI
from collector.p3_sina_preauction_probe import capture

ISSUERS = ("sh.600825", "sz.002249")
SLOTS = (
    ("pre_early", time(9, 13, 30), time(9, 14)),
    ("pre_late", time(9, 14, 20), time(9, 15)),
    ("post_control", time(9, 15, 10), time(9, 16)),
)


def now():
    return datetime.now(timezone.utc)


def run_trial(day, out, *, clock=now, wait=sleep, fetch=capture):
    start = clock().astimezone(SHANGHAI)
    if day != start.date() or day.weekday() >= 5 or not time(9, 10) <= start.time() < time(9, 15):
        raise ValueError("start on the specified weekday between 09:10 and 09:15 China time")
    out.mkdir(mode=0o700, parents=False, exist_ok=False)
    records = []
    for name, target, deadline in SLOTS:
        target_at = datetime.combine(day, target, SHANGHAI)
        deadline_at = datetime.combine(day, deadline, SHANGHAI)
        current = clock().astimezone(SHANGHAI)
        while current < target_at:
            wait(min(5, (target_at - current).total_seconds()))
            current = clock().astimezone(SHANGHAI)
        for issuer in ISSUERS:
            item = dict(slot=name, issuer=issuer)
            if clock().astimezone(SHANGHAI) >= deadline_at:
                item["result"] = "MISSED_SLOT"
            else:
                try:
                    payload = fetch(issuer)
                except (OSError, ValueError) as exc:
                    item.update(result="SOURCE_ERROR", error_type=type(exc).__name__)
                else:
                    receipt_at = datetime.fromisoformat(payload["captured_at"]).astimezone(SHANGHAI)
                    in_slot = target_at <= receipt_at < deadline_at
                    fname = f"{name}_{issuer}.json"
                    write(out / fname, payload)
                    item.update(result="CAPTURED" if in_slot else "OUTSIDE_SLOT", file=fname,
                                timing=payload["timing"], raw_sha256=payload["raw_sha256"],
                                source_time=payload["source_time"], captured_at=payload["captured_at"])
            records.append(item)
    count = sum(r["result"] == "CAPTURED" and r["slot"] != "post_control"
                and r["timing"] == "SAME_DAY_CAPTURE_BEFORE_0915" for r in records)
    summary = dict(schema="p3_preauction_trial_v1", date=day.isoformat(), records=records,
                   same_day_preauction_observations=count, preauction_visibility_certified=False,
                   historical_PIT_verified=False, trade_gate="BLOCKED", orders=[], executable_candidates=[])
    write(out / "summary.json", summary)
    return summary


def write(path, payload):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", type=date.fromisoformat, required=True)
    p.add_argument("--out", type=Path, required=True, help="new output directory on a private filesystem")
    args = p.parse_args()
    try:
        result = run_trial(args.date, args.out)
    except (ValueError, OSError) as exc:
        p.exit(1, f"Trial not completed: {exc}\n")
    print(json.dumps({"preauction_observations": result["same_day_preauction_observations"],
                      "trade_gate": result["trade_gate"]}))
    return 0 if result["same_day_preauction_observations"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
