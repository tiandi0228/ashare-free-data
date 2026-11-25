"""Bind one completed-session source receipt to the pinned P4 research window."""
import argparse
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path

from collector.p4_prewindow_evidence import verify

BEIJING = timezone(timedelta(hours=8))


def seal(run, job, manifest, raw, observed_at):
    pin = verify(run, job, manifest)
    source = json.loads(raw)
    if (source.get("phase") != "P3_TO_P4_PROSPECTIVE_HANDOFF"
            or source.get("capture_checks_all_passed") is not True
            or source.get("trade_gate") != "BLOCKED"
            or source.get("orders") != [] or source.get("executable_candidates") != []
            or source.get("historical_backtest_input_eligible") is not False):
        raise ValueError("source not a successful research-only handoff")
    day = date.fromisoformat(source["date"])
    if observed_at.utcoffset() is None:
        raise ValueError("timezone required")
    cutoff = datetime.fromisoformat(pin["window_starts_beijing"])
    observed = observed_at.astimezone(BEIJING)
    if not cutoff.date() <= day <= date.fromisoformat(pin["window_ends_beijing_inclusive"]):
        raise ValueError("outside registered window")
    if day.weekday() >= 5 or observed.date() != day or observed.time() < time(15):
        raise ValueError("same weekday after 15:00 Beijing required")
    return dict(schema="p4_daily_evidence_v1", session_date=day.isoformat(),
                observed_at=observed.isoformat(), source_sha256=hashlib.sha256(raw).hexdigest(),
                registration_sha256=pin["registration_sha256"], registration_commit=pin["registration_commit"],
                prewindow_run_id=pin["github_run_id"], source_kind="P3_PROSPECTIVE_DISCLOSURE_HANDOFF",
                session_calendar_verified=False, source_capture_attested=False,
                strategy_prices_verified=False, broker_fills_verified=0,
                prospective_OOS_validated=False, trade_gate="BLOCKED", orders=[], executable_candidates=[])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("run", "job", "manifest", "handoff", "out"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    record = seal(json.loads(a.run.read_bytes()), json.loads(a.job.read_bytes()),
                  a.manifest.read_bytes(), a.handoff.read_bytes(), datetime.now(timezone.utc))
    with a.out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
