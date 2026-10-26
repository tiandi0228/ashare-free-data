"""Research-only bounded coverage bridge: official PDF probes vs actual P1 PIT tasks."""
import argparse,json
from pathlib import Path

def overlap(worklist, source):
    if worklist.get("phase")!="P3_P1_OBSERVED_WORKLIST" or source.get("phase")!="P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE":
        raise ValueError("unexpected research inputs")
    if worklist.get("trade_gate")!="BLOCKED" or source.get("trade_gate")!="BLOCKED":
        raise ValueError("trade gate must remain blocked")
    tasks=worklist["official_evidence_tasks"]
    if len(tasks)!=worklist["official_evidence_cells_required"] or len({(x["code"],x["decision_date"],x["kind"]) for x in tasks})!=len(tasks):
        raise ValueError("invalid worklist cells")
    originals=source["sources"]
    if len({x["source_id"] for x in originals})!=len(originals):
        raise ValueError("duplicate official original")
    mapped={"IPO_LISTING":"listing","ST_CHANGE":"st","TRADING_HALT":"halt","TRADING_RESUME":"halt","DELIST_EFFECTIVE":"delisting","DELIST_RISK_ISSUER_FORECAST":"delisting"}
    available={(x["issuer"],mapped[x["event_kind"]]) for x in originals
               if x.get("original_bytes_verified") is True and x.get("event_contents_certified") is True and x["event_kind"] in mapped}
    hints=[t for t in tasks if (t["code"],t["kind"]) in available]
    return {"phase":"P3_P1_OFFICIAL_SOURCE_OVERLAP",
            "worklist_cells":len(tasks),
            "original_pdfs_content_matched":sum(x.get("event_contents_certified") is True for x in originals),
            "issuer_kind_source_overlap_cells":len(hints),
            "candidate_overlap_cells_not_pit_certified":len(hints),
            "official_pit_certified_cells":0,
            "unmatched_cells":len(tasks)-len(hints),
            "historical_publication_authenticated":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for n in ("worklist","sources","out"):p.add_argument("--"+n,required=True)
    a=p.parse_args()
    r=overlap(json.loads(Path(a.worklist).read_text()),json.loads(Path(a.sources).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":main()
