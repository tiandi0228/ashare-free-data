"""Conservative scoped semantic evidence for official date contexts.

Adjacent phrases show research hypotheses, not verified effective dates.
"""
import argparse,json,re
from pathlib import Path

PATTERNS={
 "IPO_LISTING":{"LISTING_DATE_PHRASE":r"(?:上市日期|上市时间|上市交易日|于.{0,8}上市)"},
 "ST_CHANGE":{"REVOKE_DELIST_WARNING":r"(?:撤销.{0,12}退市风险警示|退市风险警示.{0,12}撤销)",
              "CONTINUE_OTHER_WARNING":r"(?:继续实施.{0,12}其他风险警示|其他风险警示.{0,12}继续实施)",
              "IMPLEMENT_RISK_WARNING":r"(?:实施.{0,12}风险警示|被实施.{0,12}风险警示)"},
 "TRADING_HALT":{"HALT_NOTICE":r"(?:自.{0,18}起停牌|将于.{0,18}停牌|股票停牌)",
                 "RESUME_NOTICE":r"(?:自.{0,18}起复牌|将于.{0,18}复牌|股票复牌)"},
 "DELIST_RISK_ISSUER_FORECAST":{"EXPECTED_LAST_TRADING_DAY":r"(?:预计.{0,25}最后.{0,8}交易日|最后交易日预计)"},
}
def scope(q):
    if q.get("phase")!="P3_SIX_ORIGINAL_PDF_DATE_CONTEXT_INSPECTION" or q.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid original evidence")
    docs=q.get("results")
    if not isinstance(docs,list) or len(docs)!=6:raise ValueError("incomplete source evidence")
    output=[]
    for d in docs:
        patterns=PATTERNS.get(d.get("event_family"))
        if patterns is None or d.get("issuer_state_transition_authenticated") is not False:
            raise ValueError("invalid event family or prior certification")
        for ctx in d["date_contexts"]:
            raw=ctx.get("nearby_text_samples")
            if not isinstance(raw,list) or not raw:raise ValueError("missing actual context")
            hits={label:[sample[max(0,m.start()-15):min(len(sample),m.end()+15)]
                         for sample in raw for m in re.finditer(regex,sample)]
                  for label,regex in patterns.items()}
            matched=sorted(k for k,v in hits.items() if v)
            output.append({"issuer":d["issuer"],"source_id":d["source_id"],
               "date_text":ctx["date_text"],"semantic_patterns_found":matched,
               "excerpts":{k:v[:3] for k,v in hits.items() if v},
               "date_to_clause_binding_certified":False,
               "effective_day_certified":False,"historical_PIT_verified":False})
    return {"phase":"P3_SCOPED_OFFICIAL_SEMANTIC_PATTERN_REVIEW",
        "original_issuer_documents":len(docs),"date_contexts":len(output),
        "contexts_with_semantic_patterns":sum(bool(e["semantic_patterns_found"]) for e in output),
        "effective_events_certified":0,"historical_PIT_eligible":0,
        "review":output,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=scope(json.loads(Path(a.input).read_text()))
    o=Path(a.out);o.parent.mkdir(parents=True,exist_ok=True)
    o.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="review"},ensure_ascii=False))
if __name__=="__main__":main()
