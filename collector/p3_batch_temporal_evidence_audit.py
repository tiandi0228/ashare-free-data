"""Batch research evidence temporal audit: never elevate retrospective files to historical PIT."""
import argparse,json
from datetime import date
from pathlib import Path
from collector.p3_original_temporal_signal_gate import classify

def audit_batch(items):
    if not isinstance(items,list) or not items or len(items)>10000:
        raise ValueError("batch must contain between 1 and 10000 requests")
    results=[];seen=set();totals={"eligible_sources":0,"ineligible_sources":0}
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get("issuer"),str) or not isinstance(item.get("signal_date"),str):
            raise ValueError("malformed audit request")
        issuer=item["issuer"]
        day=date.fromisoformat(item["signal_date"])
        key=(issuer,day.isoformat())
        if key in seen:
            raise ValueError("duplicate issuer/date pair")
        seen.add(key)
        sources=item.get("sources")
        if not isinstance(sources,list) or not sources:
            raise ValueError("missing source evidence")
        source_ids=set()
        for source in sources:
            if not isinstance(source,dict) or not isinstance(source.get("source_id"),str) or not source["source_id"].strip():
                raise ValueError("malformed evidence identity")
            if source["source_id"] in source_ids:
                raise ValueError("duplicate source IDs within issuer/date")
            source_ids.add(source["source_id"])
        result=classify({"sources":sources},day.isoformat())
        # A single valid document can never certify complete security-state history.
        totals["eligible_sources"]+=len(result["eligible_sources"])
        totals["ineligible_sources"]+=len(result["ineligible_sources"])
        results.append({"issuer":issuer,"signal_date":day.isoformat(),
                        "eligible_sources":result["eligible_sources"],
                        "ineligible_sources":result["ineligible_sources"],
                        "issuer_full_state_history_certified":False})
    return {"phase":"P3_BATCH_TEMPORAL_EVIDENCE_AUDIT",
            "issuer_day_requests":len(results),"totals":totals,"results":results,
            "official_full_market_PIT_universe_verified":False,
            "historical_ST_halt_delist_complete":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=audit_batch(json.loads(Path(a.input).read_text()))
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10))
    print(json.dumps({k:v for k,v in result.items() if k!="results"},ensure_ascii=False))
if __name__=="__main__":main()
