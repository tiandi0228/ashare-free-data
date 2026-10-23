"""Join historical daily dates with independently attested public events, fail closed."""
import argparse,csv,json
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from collector.p3_publication_asof_gate import assess as event_asof

def join(bars_csv,events,decision_time):
    rows=list(csv.DictReader(Path(bars_csv).open(newline="")))
    if not rows or "date" not in rows[0] or "code" not in rows[0]:
        raise ValueError("historical CSV needs date and code")
    by_code=defaultdict(list)
    for row in rows:
        by_code[row["code"]].append(row)
    result=event_asof(events,decision_time)
    linked=[]
    for event in result["events"]:
        dates=[r["date"] for r in by_code.get(event["issuer"],[])]
        linked.append({"issuer":event["issuer"],"kind":event["kind"],
                       "matching_bar_rows":len(dates),
                       "rows_on_or_after_effective":sum(d>=event["effective_date"] for d in dates),
                       "known_before_decision":event["known_before_decision"],
                       "certified_issuer_day_state_rows":0,
                       "missing_authenticated_full_state":True})
    return {"phase":"P3_ASOF_EVENTS_TO_RESEARCH_BARS","event_links":linked,
            "linked_bar_rows":sum(x["matching_bar_rows"] for x in linked),
            "certified_issuer_day_state_rows":0,
            "historical_full_market_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bars",required=True);p.add_argument("--events",required=True)
    p.add_argument("--decision",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    report=join(a.bars,json.loads(Path(a.events).read_text()),a.decision)
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":main()
