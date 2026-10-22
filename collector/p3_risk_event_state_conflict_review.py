"""Fail-closed conflict review of historical risk event keyword candidates.

Keyword presence never proves risk-warning category, effective date, or PIT availability.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path

def audit(report):
    if report.get("phase")!="P3_RESEARCH_EVENT_SEMANTIC_CONTEXT_CLASSIFICATION" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("unexpected candidates")
    data=report.get("candidates")
    if not isinstance(data,list) or len(data)!=7:
        raise ValueError("expected seven original date contexts")
    output=[]; groups=defaultdict(list); seen=set()
    for r in data:
        k=(r.get("source_id"),r.get("date_text"))
        if k in seen:raise ValueError("duplicate source/date")
        seen.add(k)
        kind=r.get("event_family");words=r.get("matched_phrases",{})
        if r.get("exact_effective_date_established") is not False or r.get("tradability_certified") is not False:
            raise ValueError("candidate already inappropriately elevated")
        relevant=[w for arr in words.values() for w in arr]
        flags=[]
        if kind=="ST_CHANGE":
            flags.append("ST_WARNING_SUBTYPE_AND_DIRECTION_UNKNOWN")
            if "撤销" in relevant and "实施" in relevant:
                flags.append("ST_REVOKE_AND_APPLY_WORDS_COEXIST")
        elif kind=="TRADING_HALT":
            flags.append("HALT_RESUME_DAY_ROLE_NOT_AUTHENTICATED")
            if "停牌" in relevant and "复牌" in relevant:
                flags.append("HALT_AND_RESUME_WORDS_COEXIST")
        elif kind=="DELIST_RISK_ISSUER_FORECAST":
            flags.append("FORECAST_NOT_EXCHANGE_EFFECTIVE_DELIST")
        elif kind=="IPO_LISTING":
            flags.append("LISTING_WORDS_NOT_FULL_RISK_STATE")
        else:raise ValueError("unrecognized family")
        output.append({"issuer":r["issuer"],"source_id":k[0],"date_text":k[1],
                       "family":kind,"manual_review_flags":flags,
                       "state_change_direction":"UNKNOWN","certified_effective_date":None,
                       "PIT_eligible":False})
        groups[k[0]].append(k[1])
    return {"phase":"P3_CONSERVATIVE_EVENT_STATE_CONFLICT_REVIEW",
       "date_candidates":len(output),"documents":len(groups),
       "multi_date_documents":sum(len(v)>1 for v in groups.values()),
       "flagged_candidates":sum(bool(r["manual_review_flags"]) for r in output),
       "confirmed_effective_state_changes":0,"PIT_eligible_count":0,
       "reviews":output,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=audit(json.loads(Path(a.input).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="reviews"},ensure_ascii=False))
if __name__=="__main__":main()
