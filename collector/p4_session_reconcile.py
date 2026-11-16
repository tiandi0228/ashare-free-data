"""Reconcile research handoffs against the notice-covered part of the P4 window."""
import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path

from collector.p4_daily_evidence import BEIJING, seal
from collector.p4_prewindow_evidence import verify

SSE_2026 = "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml"


def calendar(day):
    if day.weekday() >= 5:
        return "WEEKEND_CLOSED"
    if date(2026, 12, 1) <= day <= date(2026, 12, 31):
        return "EXPECTED_SSE_SESSION"
    return "CALENDAR_UNVERIFIED"


def reconcile(run, job, manifest, submissions, now):
    if now.utcoffset() is None:
        raise ValueError("timezone required")
    pin = verify(run, job, manifest)
    day = datetime.fromisoformat(pin["window_starts_beijing"]).date()
    end = date.fromisoformat(pin["window_ends_beijing_inclusive"])
    now = now.astimezone(BEIJING)
    valid = {}
    for record, raw in submissions:
        at = datetime.fromisoformat(record["observed_at"])
        rebuilt = seal(run, job, manifest, raw, at)
        d = date.fromisoformat(rebuilt["session_date"])
        if rebuilt != record or at > now or calendar(d) != "EXPECTED_SSE_SESSION" or d in valid:
            raise ValueError("invalid, future, unverified-calendar or duplicate receipt")
        valid[d] = rebuilt["source_sha256"]
    rows = []
    while day <= end:
        status = calendar(day)
        if status == "EXPECTED_SSE_SESSION":
            if day in valid:
                status = "RETAINED"
            elif now.date() > day:
                status = "MISSING"
            else:
                status = "PENDING"
        rows.append(dict(date=day.isoformat(), status=status, source_sha256=valid.get(day)))
        day += timedelta(days=1)
    return dict(schema="p4_session_reconcile_v1", calendar_notice=SSE_2026, rows=rows,
                counts={s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
                official_calendar_fully_verified=False, prospective_OOS_validated=False,
                broker_fills_verified=0, trade_gate="BLOCKED", orders=[], executable_candidates=[])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--submission", type=Path, nargs=2, action="append", default=[],
                   metavar=("RECEIPT", "HANDOFF"))
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = reconcile(json.loads(a.run.read_bytes()), json.loads(a.job.read_bytes()),
                       a.manifest.read_bytes(),
                       [(json.loads(r.read_bytes()), source.read_bytes()) for r, source in a.submission],
                       datetime.now(timezone.utc))
    with a.out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
