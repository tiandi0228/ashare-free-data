"""Generate real issuer/event research targets from audited P1-P3 overlap, no invented URLs."""
import argparse,json
from collections import Counter
from pathlib import Path
from collector.p3_official_scope_overlap import overlap

def targets(worklist,originals):
    report=overlap(worklist,originals)
    matched=set()
    mapping={"IPO_LISTING":"listing","ST_CHANGE":"st","TRADING_HALT":"halt",
             "TRADING_RESUME":"halt","DELIST_EFFECTIVE":"delisting",
             "DELIST_RISK_ISSUER_FORECAST":"delisting"}
    for r in originals["sources"]:
        if r.get("original_bytes_verified") is True and r.get("event_contents_certified") is True and r.get("event_kind") in mapping:
            matched.add((r["issuer"],mapping[r["event_kind"]]))
    missing=[t for t in worklist["official_evidence_tasks"] if (t["code"],t["kind"]) not in matched]
    counts=Counter((t["code"],t["kind"]) for t in missing)
    queue=[{"issuer":code,"event_kind":kind,"observed_decision_dates":sorted({t["decision_date"] for t in missing if t["code"]==code and t["kind"]==kind}),
            "cells_to_research":n,"original_official_url":None,"original_publication_time":None,
            "research_state":"SOURCE_DISCOVERY_REQUIRED_NOT_CERTIFIED"}
           for (code,kind),n in sorted(counts.items())]
    if sum(x["cells_to_research"] for x in queue)!=report["unmatched_cells"]:
        raise ValueError("unmatched cell accounting mismatch")
    return {"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
            "source_roster_sha256":worklist.get("source_sha256"),
            "unmatched_issuer_kind_targets":len(queue),
            "unmatched_cells":report["unmatched_cells"],
            "targets":queue,"official_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for x in ("worklist","sources","out"):p.add_argument("--"+x,required=True)
    a=p.parse_args()
    r=targets(json.loads(Path(a.worklist).read_text()),json.loads(Path(a.sources).read_text()))
    d=Path(a.out);d.parent.mkdir(parents=True,exist_ok=True)
    d.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="targets"}))
if __name__=="__main__":main()
