"""Convert real free official PDF receipts to typed research-only risk cues.

Text co-occurrence does NOT authenticate the precise effective day or
historical ST / halt / delisting completeness.
"""
import argparse,json
from pathlib import Path
from datetime import datetime

def normalize(q):
    if q.get("phase")!="P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE" or q.get("trade_gate")!="BLOCKED":
        raise ValueError("unexpected original receipt")
    sources=q.get("sources")
    if not isinstance(sources,list) or not sources or len(sources)!=q.get("source_count"):
        raise ValueError("inconsistent original count")
    rows=[];seen=set()
    for s in sources:
        sid=s.get("source_id");code=s.get("issuer");kind=s.get("event_kind")
        if not sid or sid in seen:
            raise ValueError("duplicated original source identity")
        seen.add(sid)
        verified=(s.get("original_bytes_verified") is True and
                  s.get("event_contents_certified") is True and
                  s.get("issuer_text_present") is True and
                  bool(s.get("sha256")) and
                  s.get("PIT_publication_verified") is False)
        status="RETROSPECTIVE_CONTENT_ONLY" if verified else "UNVERIFIED_OR_UNAVAILABLE"
        observed=s.get("observed_at_utc")
        if observed is not None:
            value=datetime.fromisoformat(observed.replace("Z","+00:00"))
            if value.tzinfo is None:
                raise ValueError("naive acquisition time")
        rows.append({"source_id":sid,"issuer":code,"event_kind":kind,
                     "evidence_level":status,"original_sha256":s.get("sha256"),
                     "actual_acquired_at_utc":observed,
                     "event_effective_date_certified":False,
                     "historical_PIT_publication_verified":False,
                     "historical_ST_halt_delist_coverage_certified":False,
                     "usable_for_historical_trade_signal":False})
    return {"phase":"P3_FREE_MULTI_ISSUER_RESEARCH_EVIDENCE_LEDGER",
            "source_count":len(rows),
            "retrospective_content_verified":sum(r["evidence_level"]=="RETROSPECTIVE_CONTENT_ONLY" for r in rows),
            "historically_eligible_event_count":0,
            "event_type_counts":{kind:sum(r["event_kind"]==kind for r in rows) for kind in sorted({r["event_kind"] for r in rows})},
            "events":rows,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=normalize(json.loads(Path(a.input).read_text()))
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10))
    print(json.dumps({k:v for k,v in result.items() if k!="events"},ensure_ascii=False))
if __name__=="__main__":main()
