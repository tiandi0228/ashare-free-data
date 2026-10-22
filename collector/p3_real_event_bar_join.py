"""Retrospectively join verified official effective-date events to real source dates.

Never infer trade eligibility or complete risk history from event intervals.
"""
import argparse,csv,json
from collections import defaultdict,Counter
from datetime import date
from pathlib import Path
from collector.p1_128_source_replay_audit import audit
from collector.p3_real_issuer_day_pit_coverage import MANIFEST_SHA

def join(root, inventory):
    replay=audit(root,expected_manifest_sha=MANIFEST_SHA)
    if (inventory.get("phase")!="P3_TWO_ISSUER_OFFICIAL_EVENT_RETROSPECTIVE_INVENTORY" or
        inventory.get("retrospective_official_events")!=2 or
        inventory.get("historical_PIT_eligible_events")!=0 or
        inventory.get("trade_gate")!="BLOCKED"):
        raise ValueError("official evidence inventory contract mismatch")
    events=inventory.get("events")
    if not isinstance(events,list) or len(events)!=2:
        raise ValueError("expected precisely two distinct original events")
    by_issuer=defaultdict(list);seen=set()
    for e in events:
        key=(e.get("issuer"),e.get("kind"),e.get("effective_date_as_stated"))
        if key in seen:
            raise ValueError("duplicate original evidence event")
        seen.add(key)
        if (e.get("original_bytes_verified") is not True or
            e.get("official_content_verified") is not True or
            e.get("issuer_day_state_PIT_eligible") is not False):
            raise ValueError("invalid provenance or PIT elevation")
        date.fromisoformat(e["effective_date_as_stated"])
        by_issuer[e["issuer"]].append(e)
    counts=Counter();present=set();source_rows=0;date_spans={}
    for receipt in Path(root).rglob("quality.json"):
        q=json.loads(receipt.read_text())
        for entry in q["issuer_receipts"]:
            code=entry["code"];present.add(code)
            with (receipt.parent/(code.replace(".","_")+".csv")).open(newline="") as fh:
                rows=list(csv.DictReader(fh))
            source_rows+=len(rows)
            if rows:
                dates=[r["date"] for r in rows]
                date_spans[code]=(min(dates),max(dates))
            for row in rows:
                for e in by_issuer.get(code,[]):
                    before=row["date"]<e["effective_date_as_stated"]
                    counts[(code,e["kind"],"BEFORE" if before else "ON_OR_AFTER")]+=1
    if source_rows!=replay["historical_rows"]:
        raise ValueError("source row count changed")
    joined=[];unmatched=[]
    for e in events:
        code=e["issuer"]
        if code not in present:
            unmatched.append({"issuer":code,"event_kind":e["kind"],
                              "reason":"NOT_IN_FROZEN_128_RESEARCH_SAMPLE"})
            continue
        first,last=date_spans[code]
        effective=e["effective_date_as_stated"]
        relation=("BEFORE_SOURCE_WINDOW" if effective<first else
                  "AFTER_SOURCE_WINDOW" if effective>last else
                  "WITHIN_SOURCE_WINDOW")
        joined.append({"issuer":code,"event_kind":e["kind"],
                       "source_first_day":first,"source_last_day":last,
                       "effective_date_relation_to_source_window":relation,
                       "effective_day":e["effective_date_as_stated"],
                       "before_effective_source_rows":counts[(code,e["kind"],"BEFORE")],
                       "on_or_after_effective_source_rows":counts[(code,e["kind"],"ON_OR_AFTER")],
                       "proven_asof_at_historical_day":False,
                       "certified_tradable_rows":0})
    return {"phase":"P3_REAL_OFFICIAL_EVENT_TO_RESEARCH_BARS_JOIN",
            "sample_issuer_count":replay["verified_unique_issuers"],
            "sample_source_rows":source_rows,
            "official_verified_event_count":len(events),
            "joined_events":joined,"events_not_in_sample":unmatched,
            "event_sample_disposition_counts":{
                "IN_SAMPLE_WITH_BARS":len(joined),
                "OUTSIDE_FROZEN_SAMPLE":len(unmatched),
                "IN_SAMPLE_NO_BARS":0},
            "frozen_sample_scope_only":True,
            "historical_point_in_time_risk_coverage_rows":0,
            "historical_full_market_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--bars",required=True)
    p.add_argument("--inventory",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    q=join(a.bars,json.loads(Path(a.inventory).read_text()))
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+chr(10))
    print(json.dumps(q,ensure_ascii=False))
if __name__=="__main__":main()
