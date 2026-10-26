"""Quarantined text-neighborhood classification for real P1 official PDF dates."""
import argparse,json
from pathlib import Path
RULES={"TRADING_HALT_CUE":("停牌","暂停交易"),
       "TRADING_RESUME_CUE":("复牌","恢复交易"),
       "ST_RISK_CUE":("风险警示","*ST","实施ST"),
       "DELIST_CUE":("退市","终止上市"),
       "LISTING_CUE":("上市日期","上市交易")}
def classify(report):
    if report.get("phase")!="P3_REAL_P1_PDF_TEXT_RESEARCH_CUES" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("unexpected provenance")
    rows=[]
    for doc in report["sources"]:
        if doc.get("historical_PIT_verified") is not False or doc.get("event_effective_date_certified") is not False:
            raise ValueError("unsupported historical promotion")
        for item in doc.get("date_contexts_research_only",[]):
            if item.get("effective_date_certified") is not False:raise ValueError("invalid date certification")
            context=item["source_text_context"]
            if not isinstance(context,str) or len(context)>200:raise ValueError("oversized context")
            labels=[k for k,words in RULES.items() if any(w in context for w in words)]
            rows.append({"issuer":doc["issuer"],"announcement_id":doc["announcement_id"],
                         "original_sha256":doc["original_sha256"],"date_text":item["date_text"],
                         "candidate_event_cues":labels or ["NO_SPECIFIC_CUE"],
                         "source_text_context":context,"human_review_required":True,
                         "historical_effective_date_verified":False,
                         "historical_publication_time_verified":False})
    return {"phase":"P3_REAL_P1_DATE_CONTEXT_TRIAGE","research_date_context_count":len(rows),
            "candidate_contexts":rows,"historical_issuer_states_certified":0,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    q=classify(json.loads(Path(a.source).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":q["phase"],"research_date_context_count":q["research_date_context_count"],
                      "historical_issuer_states_certified":0}))
if __name__=="__main__":main()
