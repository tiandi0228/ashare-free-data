"""Join historical daily dates with independently attested public events, fail closed."""
import argparse,csv,json
from pathlib import Path
from collections import defaultdict
from datetime import date
from zoneinfo import ZoneInfo
from collector.p3_publication_asof_gate import assess as event_asof, instant


def join(bars_csv, events, decision_time):
    """Separate archive-wide links from strictly prior session dates.

    Prior-session rows are only a date-bounded subset, not proof of vendor
    availability at the decision instant. A daily row has no intraday clock,
    including when the decision is after the scheduled close.
    """
    result = event_asof(events, decision_time)
    decision_day = instant(decision_time).astimezone(ZoneInfo("Asia/Shanghai")).date()
    by_code = defaultdict(list)
    seen = set()
    with Path(bars_csv).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not {"date", "code"} <= set(reader.fieldnames):
            raise ValueError("historical CSV needs date and code")
        for row in reader:
            stamp, code = row["date"], row["code"]
            if not code or not stamp:
                raise ValueError("missing issuer or session date")
            day = date.fromisoformat(stamp)
            if day.isoformat() != stamp or (code, day) in seen:
                raise ValueError("noncanonical session date or duplicate issuer/day bar")
            seen.add((code, day))
            by_code[code].append(day)
    if not seen:
        raise ValueError("historical CSV is empty")
    linked = []
    for event in result["events"]:
        days = by_code.get(event["issuer"], [])
        effective_day = date.fromisoformat(event["effective_date"])
        linked.append({
            "issuer": event["issuer"], "kind": event["kind"],
            "matching_bar_rows": len(days),
            "rows_on_or_after_effective": sum(day >= effective_day for day in days),
            "prior_session_bar_rows": sum(day < decision_day for day in days),
            "decision_day_bar_rows_without_availability_clock": sum(day == decision_day for day in days),
            "future_session_bar_rows": sum(day > decision_day for day in days),
            "known_before_decision": event["known_before_decision"],
            "effective_by_decision_instant": event["effective_by_decision_instant"],
            "certified_issuer_day_state_rows": 0,
            "missing_authenticated_full_state": True,
        })
    return {
        "phase": "P3_ASOF_EVENTS_TO_RESEARCH_BARS", "event_links": linked,
        "decision_session_day_shanghai": decision_day.isoformat(),
        "linked_bar_rows": sum(x["matching_bar_rows"] for x in linked),
        "linked_bar_rows_are_archive_wide": True,
        "prior_session_rows_prove_asof_availability": False,
        "certified_issuer_day_state_rows": 0, "historical_full_market_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bars",required=True);p.add_argument("--events",required=True)
    p.add_argument("--decision",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    report=join(a.bars,json.loads(Path(a.events).read_text()),a.decision)
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":main()
