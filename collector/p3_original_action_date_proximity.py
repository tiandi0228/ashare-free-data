"""Extract event-action proximity from hash-verified original PDF contexts.

Date/action proximity is a candidate, never certified effective-date semantics.
"""
import argparse,json,re
from pathlib import Path

ACTIONS={"ST_CHANGE":{"REVOKE_DELIST_WARNING":"撤销退市风险警示","REVOKE_OTHER_WARNING":"撤销其他风险警示","APPLY_OTHER_WARNING":"实施其他风险警示","APPLY_DELIST_WARNING":"实施退市风险警示"},"TRADING_HALT":{"HALT":"停牌","RESUME":"复牌"},"IPO_LISTING":{"LISTING":"上市交易"},"DELIST_RISK_ISSUER_FORECAST":{"FORECAST":"预计"}}
def extract(report):
    if not isinstance(report,dict):
        raise ValueError("invalid original PDF report")
    if report.get("phase")!="P3_SIX_ORIGINAL_PDF_DATE_CONTEXT_INSPECTION" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("wrong original PDF context phase")
    docs=report.get("results",[])
    if not isinstance(docs,list) or len(docs)!=6 or any(not isinstance(doc,dict) for doc in docs):
        raise ValueError("missing or malformed original PDF evidence")
    source_ids=[doc.get("source_id") for doc in docs]
    if any(not isinstance(s,str) or not s.strip() for s in source_ids) or len(set(source_ids))!=len(source_ids):
        raise ValueError("missing or duplicate original source IDs")
    if any(not isinstance(doc.get("issuer"),str) or not doc["issuer"].strip() for doc in docs):
        raise ValueError("missing original issuer")
    output=[]
    for doc in docs:
        actions=ACTIONS.get(doc.get("event_family"))
        if not actions:raise ValueError("unknown family")
        contexts=doc.get("date_contexts")
        if not isinstance(contexts,list) or not contexts:
            raise ValueError("original date contexts missing")
        for d in contexts:
            if not isinstance(d,dict) or not isinstance(d.get("date_text"),str) or not d["date_text"].strip():
                raise ValueError("invalid original date")
            samples=d.get("nearby_text_samples",[])
            if not isinstance(samples,list) or not samples or any(not isinstance(s,str) or not s for s in samples):
                raise ValueError("original context missing")
            hits=[]
            for sample in samples:
                if d["date_text"] not in sample:
                    raise ValueError("date/context mismatched")
                # Never join a date and an event verb across sentence or clause boundaries.
                for clause in re.split(r"[。！？；;\n]",sample):
                    positions=[m.start() for m in re.finditer(re.escape(d["date_text"]),clause)]
                    if not positions:
                        continue
                    for label,word in actions.items():
                        for m in re.finditer(re.escape(word),clause):
                            gap=min(min(abs(m.start()-position),abs(m.end()-position)) for position in positions)
                            if gap<=80:
                                hits.append({"action":label,"phrase":word,"character_gap":gap})
            labels=sorted(set(x["action"] for x in hits))
            output.append({"issuer":doc["issuer"],"source_id":doc["source_id"],
                "date_text":d["date_text"],"nearby_action_labels":labels,
                "action_proximity_details":hits[:25],
                "multiple_action_directions":len(labels)>1,
                "verified_effective_state_transition":False,
                "historical_PIT_publication_verified":False})
    return {"phase":"P3_ORIGINAL_ACTION_DATE_PROXIMITY_RESEARCH","source_documents":len(docs),
        "date_candidates":len(output),"dates_with_nearby_actions":sum(bool(x["nearby_action_labels"]) for x in output),
        "date_candidates_with_multiple_action_labels":sum(x["multiple_action_directions"] for x in output),
        "certified_effective_state_transitions":0,"historical_PIT_eligible":0,
        "candidates":output,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=extract(json.loads(Path(a.input).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="candidates"},ensure_ascii=False))
if __name__=="__main__":main()
