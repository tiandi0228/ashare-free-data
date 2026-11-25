"""Route the verified 000582 PDF pair through the historical research gates."""
from pathlib import Path
import hashlib

from collector.p3_000582_halt_replay import HALT, RESUME, ISSUER, SOURCES, VENDOR_SHA
from collector.p3_000582_publication_clock import INDEX
from collector.p3_publication_asof_gate import assess
from collector.p3_publication_bar_gap import join
from collector.p3_publication_proof_task_queue import build

DECISIONS = (
    "2026-10-08T09:30:00+08:00",
    "2026-10-11T23:59:00+08:00",
    "2026-10-12T09:30:00+08:00",
)


def replay_clock(clock, bars):
    if (clock.get("phase") != "P3_000582_PUBLICATION_CLOCK_AUDIT"
            or clock.get("trade_gate") != "BLOCKED" or clock.get("orders") != []
            or clock.get("executable_candidates") != []
            or clock.get("historical_PIT_verified") is not False
            or clock.get("historical_decision_time_eligibility_verified") is not False
            or clock.get("index_value_is_not_first_publication_time") is not True):
        raise ValueError("unsafe retrospective clock report")
    notices = clock["notices"]
    if set(notices) != {"halt", "resume"}:
        raise ValueError("wrong scope of publication clock")
    events = []
    for label, kind, day in (("halt", "HALT_START", HALT), ("resume", "RESUME_START", RESUME)):
        pdf = notices[label]
        if (pdf.get("original_sha256") != SOURCES[label][1]
                or pdf.get("announcement_id") != INDEX[label][0]
                or pdf.get("index_date_beijing") != INDEX[label][1]
                or pdf.get("first_publication_time_verified") is not False):
            raise ValueError("changed source identity or unsupported publication claim")
        events.append({
            "issuer": ISSUER, "kind": kind, "effective_date": day,
            "original_sha256": pdf["original_sha256"], "original_bytes_verified": True,
            # This fixture identifies the official-hosted PDF. Index metadata and
            # news coverage never become an authenticated first-publication instant.
            "publisher_independently_authenticated": True,
            "authenticated_first_published_at": None,
            "publication_timestamp_independently_authenticated": False,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        })
    if hashlib.sha256(Path(bars).read_bytes()).hexdigest() != VENDOR_SHA:
        raise ValueError("wrong pinned vendor bars")
    cases = []
    for instant in DECISIONS:
        asof = assess(events, instant)
        queue = build(asof)
        joined = join(bars, events, instant)
        if (asof["known_event_count"] != 0 or queue["task_count"] != len(events)
                or joined["certified_issuer_day_state_rows"] != 0
                or any(row["known_before_decision"] or row["effective_by_decision_instant"]
                       for row in joined["event_links"])):
            raise ValueError("retrospective event crossed the historical decision boundary")
        cases.append(dict(decision_beijing=instant, asof=asof, proof_queue=queue, bar_audit=joined))
    return dict(phase="P3_000582_HISTORICAL_DECISION_REPLAY", issuer=ISSUER, cases=cases,
                historical_PIT_verified=False, trade_gate="BLOCKED", orders=[], executable_candidates=[])
