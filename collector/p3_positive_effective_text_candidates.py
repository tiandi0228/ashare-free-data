"""Conservative positive event-date semantics from SHA-replayed PDF excerpt windows.

A retrospective effective-date assertion is distinct from historical point-in-time
availability and from complete ST/suspension/delisting state certification.
"""
import argparse,json,re
from pathlib import Path

RULES={
 "IPO_LISTING": {"LISTING_START":(r"(?:于|自|在)?{day}(?:起|开始)?(?:在[^。；]{0,12})?上市(?:交易)?",r"上市(?:交易)?(?:日期|时间)?(?:为|：|:)?{day}")},
 "TRADING_HALT":{"HALT_START":(r"(?:自|于){day}起?停牌",r"{day}(?:开市起)?停牌"),
                 "RESUME_START":(r"(?:自|于){day}起?复牌",r"{day}(?:开市起)?复牌")},
 "ST_CHANGE":{"ST_WARNING_APPLIED":(r"(?:自|于){day}起(?:被)?实施(?:其他)?风险警示",),
              "ST_WARNING_REMOVED":(r"(?:自|于){day}起撤销(?:退市|其他)?风险警示",)},
}
def check_text(kind,day,text):
    if kind=="DELIST_RISK_ISSUER_FORECAST":
        return {"candidate":None,"reason":"FORECAST_IS_NOT_EXCHANGE_EFFECTIVE_DELIST"}
    patterns=RULES.get(kind)
    if not patterns:raise ValueError("unsupported event kind")
    found=[]
    escaped=re.escape(day)
    for direction,expressions in patterns.items():
        if any(re.search(p.replace("{day}",escaped),text) for p in expressions):
            found.append(direction)
    if len(set(found))!=1:
        return {"candidate":None,"reason":"NO_EXPLICIT_SINGLE_DATE_DIRECTION" if not found else "MULTIPLE_EVENT_DIRECTIONS"}
    # A snippet can establish textual assertion, never complete risk regime.
    return {"candidate":found[0],"reason":"EXPLICIT_LOCAL_TEXT_ASSERTION_RESEARCH_ONLY"}

def build(report):
    if report.get("phase")!="P3_SIX_ORIGINAL_PDF_DATE_CONTEXT_INSPECTION" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid source context receipt")
    docs=report.get("results")
    if not isinstance(docs,list) or len(docs)!=6:raise ValueError("expected six originals")
    rows=[];seen=set()
    for d in docs:
        sid=d["source_id"]
        if sid in seen or not re.fullmatch(r"[a-f0-9]{64}",d.get("original_sha256","")):
            raise ValueError("duplicate/malformed source hash identity")
        seen.add(sid)
        if d.get("issuer_state_transition_authenticated") is not False:
            raise ValueError("previous stage overcertified")
        for item in d["date_contexts"]:
            day=item["date_text"]
            if not re.fullmatch(r"20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日",day):raise ValueError("malformed cue")
            snippets=item["nearby_text_samples"]
            if not snippets or item.get("effective_date_certified") is not False:
                raise ValueError("missing context or prior false certification")
            verdicts=[check_text(d["event_family"],day,s) for s in snippets]
            directions={x["candidate"] for x in verdicts if x["candidate"]}
            # Distinct opposite directions, or conflicting unrelated dates in
            # nearby snippets require review, never silent certification.
            direction=next(iter(directions)) if len(directions)==1 else None
            rows.append({"source_id":sid,"issuer":d["issuer"],"date_text":day,
                         "event_family":d["event_family"],
                         "explicit_local_date_direction":direction,
                         "textual_assertion_candidate":direction is not None,
                         "manual_review_required":direction is None or len(directions)>1,
                         "effective_day_independently_certified":False,
                         "historical_publication_timestamp_certified":False,
                         "historical_trade_eligible":False})
    return {"phase":"P3_POSITIVE_ORIGINAL_EFFECTIVE_TEXT_CANDIDATES",
            "source_count":len(seen),"date_cues":len(rows),
            "local_assertion_candidates":sum(x["textual_assertion_candidate"] for x in rows),
            "official_PIT_trade_eligible":0,
            "candidates":rows,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=build(json.loads(Path(a.input).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="candidates"},ensure_ascii=False))
if __name__=="__main__":main()
