"""Classify archived original-PDF date surroundings as review cues, never PIT states."""
import argparse,json
from pathlib import Path

PHRASES={
 "IPO_LISTING":{"LISTING_MENTION":("上市交易","上市日期","上市时间")},
 "DELIST_RISK_ISSUER_FORECAST":{"FORECAST_FINAL_TRADE":("最后交易日","最后一个交易日","预计","终止上市")},
 "ST_CHANGE":{"ST_WARNING_CONTEXT":("风险警示","撤销","实施")},
 "TRADING_HALT":{"HALT_CONTEXT":("停牌","复牌")},
}
def classify(report):
    if report.get("phase")!="P3_SIX_ORIGINAL_PDF_DATE_CONTEXT_INSPECTION" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("unrecognized original context report")
    docs=report.get("results")
    if not isinstance(docs,list) or len(docs)!=6 or report.get("verified_originals")!=6:
        raise ValueError("incomplete six-source evidence")
    seen=set();out=[]
    for doc in docs:
        source=doc.get("source_id")
        if not isinstance(source,str) or source in seen:raise ValueError("duplicate source")
        seen.add(source)
        kind=doc.get("event_family")
        if kind not in PHRASES:raise ValueError("unsupported event family")
        if doc.get("issuer_state_transition_authenticated") is not False:raise ValueError("unsupported certification")
        contexts=doc.get("date_contexts")
        if not contexts:raise ValueError("missing extracted original contexts")
        for row in contexts:
            samples=row.get("nearby_text_samples")
            if not isinstance(samples,list) or not samples:raise ValueError("missing context excerpts")
            votes={label:sorted({word for word in words if any(word in t for t in samples)})
                   for label,words in PHRASES[kind].items()}
            matched=[label for label,words in votes.items() if words]
            out.append({"issuer":doc["issuer"],"source_id":source,"event_family":kind,
                        "date_text":row["date_text"],"research_cues":matched,
                        "matched_phrases":votes,
                        "semantic_evidence_status":"KEYWORD_CONTEXT_ONLY" if matched else "NO_EVENT_CONTEXT_KEYWORD",
                        "exact_effective_date_established":False,
                        "historical_publication_instant_verified":False,
                        "tradability_certified":False})
    return {"phase":"P3_RESEARCH_EVENT_SEMANTIC_CONTEXT_CLASSIFICATION",
            "source_documents":len(seen),"dated_contexts":len(out),
            "date_contexts_with_event_keywords":sum(bool(x["research_cues"]) for x in out),
            "effective_events_certified":0,"historical_PIT_eligible_events":0,
            "candidates":out,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();q=classify(json.loads(Path(a.input).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in q.items() if k!="candidates"},ensure_ascii=False))
if __name__=="__main__":main()
