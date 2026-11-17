"""Reconcile research handoffs against the notice-covered part of the P4 window."""
import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path

from collector.p4_daily_evidence import BEIJING, seal
from collector.p4_prewindow_evidence import verify

CALENDAR_NOTICES = {
    "SSE": "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml",
    "SZSE": "https://www.szse.cn/disclosure/notice/t20251222_618087.html",
}
NOTICE_SCOPE_START = date(2026, 12, 1)
NOTICE_SCOPE_END = date(2026, 12, 31)
SESSION_CLOSE_BEIJING = time(15)
EXPECTED_SESSION = "EXPECTED_HS_SESSION"


def calendar(day):
    if day.weekday() >= 5:
        return "WEEKEND_CLOSED"
    if NOTICE_SCOPE_START <= day <= NOTICE_SCOPE_END:
        return EXPECTED_SESSION
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
        if rebuilt != record or at > now or calendar(d) != EXPECTED_SESSION or d in valid:
            raise ValueError("invalid, future, unverified-calendar or duplicate receipt")
        valid[d] = rebuilt["source_sha256"]
    rows = []
    while day <= end:
        status = calendar(day)
        if status == EXPECTED_SESSION:
            if day in valid:
                status = "RETAINED"
            elif now.date() > day:
                status = "NOT_IN_SUBMITTED_RUNS" if valid else "NOT_CHECKED"
            elif day > now.date() or now.time() < SESSION_CLOSE_BEIJING:
                status = "PENDING_SESSION_CLOSE"
            else:
                status = "AWAITING_RECEIPT"
        rows.append(dict(date=day.isoformat(), status=status, source_sha256=valid.get(day)))
        day += timedelta(days=1)
    counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    return dict(schema="p4_session_reconcile_v2", calendar_notices=CALENDAR_NOTICES.copy(),
                calendar_notice_scope=dict(start=NOTICE_SCOPE_START.isoformat(),
                                           end=NOTICE_SCOPE_END.isoformat()),
                coverage_scope="SUBMITTED_RUNS_ONLY" if valid else "CALENDAR_ONLY",
                as_of_beijing=now.isoformat(), rows=rows, counts=counts,
                window_coverage=_window_coverage(rows),
                official_calendar_fully_verified=False, prospective_OOS_validated=False,
                broker_fills_verified=0, trade_gate="BLOCKED", orders=[], executable_candidates=[])


def _window_coverage(rows):
    groups = {
        "retained": ("RETAINED",),
        "closed_awaiting_receipt": ("AWAITING_RECEIPT",),
        "past_not_in_submitted_runs": ("NOT_IN_SUBMITTED_RUNS",),
        "past_not_checked": ("NOT_CHECKED",),
        "pending_close": ("PENDING_SESSION_CLOSE",),
        "calendar_unverified": ("CALENDAR_UNVERIFIED",),
        "weekend_closed": ("WEEKEND_CLOSED",),
    }
    days = {key: [row["date"] for row in rows if row["status"] in states]
            for key, states in groups.items()}
    elapsed = sum(len(days[key]) for key in ("retained", "closed_awaiting_receipt",
                                             "past_not_in_submitted_runs", "past_not_checked"))
    return {
        "window_start_beijing": rows[0]["date"],
        "window_end_beijing_inclusive": rows[-1]["date"],
        "calendar_days": len(rows),
        "notice_scoped_expected_sessions": elapsed + len(days["pending_close"]),
        "notice_scoped_sessions_past_close": elapsed,
        "retained_sessions": len(days["retained"]),
        "retained_fraction_of_notice_scoped_sessions_past_close":
            len(days["retained"]) / elapsed if elapsed else None,
        "dates_by_status": days,
        "not_in_submitted_runs_is_not_proof_of_missing_receipt": True,
    }


def attach_run_provenance(report, checks):
    """Link verified Actions artifacts to retained dates, never by list position."""
    rows = {row["date"]: row for row in report["rows"] if row["status"] == "RETAINED"}
    by_date = {}
    artifacts = set()
    runs = set()
    for check in checks:
        day = check["session_date"]
        artifact = check["artifact_id"]
        run = check["run_id"]
        if (day in by_date or artifact in artifacts or run in runs or day not in rows
                or check["source_sha256"] != rows[day]["source_sha256"]):
            raise ValueError("disclosure provenance does not match unique retained sessions")
        by_date[day] = check
        artifacts.add(artifact)
        runs.add(run)
    if by_date.keys() != rows.keys():
        raise ValueError("a retained session is missing verified Actions provenance")
    return {**report, "rows": [
        {**row, "actions_provenance": by_date.get(row["date"])}
        for row in report["rows"]
    ]}


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
