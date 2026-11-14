"""Fail-closed integration of existing P4 dual-horizon research categories and ST veto.

Only joins offline research assessments with independently wired issuer-notice
research guard; provides no trading eligibility or actual exchange PIT proof.
Do not use optimistic dual-horizon categories to bypass dated ST exclusion.
"""
import argparse
import json
from datetime import date
from pathlib import Path
from collector.p4_dual_horizon_research import assess
from collector.p4_historical_st_research_veto import classify as historical_veto

PHASE="P4_DUAL_HORIZON_DATED_ST_END_TO_END_RESEARCH_GATE"
RISK={
    "VETO_ISSUER_NOTICE_SUSPENDED_DAY",
    "VETO_ISSUER_NOTICE_ST_EFFECTIVE",
}
ALLOWED={
    "UNKNOWN_PIT_STATUS_FAIL_CLOSED",
    "PRE_ST_NOTICE_INTERVAL_NOT_PIT_AUTHENTICATED",
    *RISK,
}

def integrate(source, research_evidence, observations):
    # These are *synthetic* as-of examples and issuer source crosswalks, not
    # a certified historical ST roster or independently published PIT history.
    if not isinstance(research_evidence,dict) or not isinstance(observations,list):
        raise ValueError("invalid end-to-end research evidence")
    veto=historical_veto(source,observations)
    if (veto.get("historical_PIT_verified") is not False
        or veto.get("production_trade_gate_implementation_verified") is not False
        or veto.get("trade_gate")!="BLOCKED"
        or veto.get("approved_entries")!=0
        or veto.get("orders")!=[]
        or veto.get("executable_candidates")!=[]):
        raise ValueError("unsafe historical veto evidence")
    research=assess(research_evidence)
    if (research.get("phase")!="P4_DUAL_HORIZON_INDEPENDENT_RESEARCH_SCREEN"
        or research.get("trade_gate")!="BLOCKED"
        or research.get("buy_recommendations_authorized") is not False
        or research.get("historical_PIT_verified") is not False
        or research.get("orders")!=[]
        or research.get("executable_candidates")!=[]):
        raise ValueError("unsafe research suitability")
    if research.get("asof")!=observations[0].get("signal_known_after_close_date"):
        raise ValueError("source as-of day differs from one-day research input")
    if any(o.get("signal_known_after_close_date")!=research["asof"] for o in observations):
        raise ValueError("multi-day replay requires separately certified daily joins")
    rows=research.get("symbols")
    states=veto.get("research_decisions")
    if (not isinstance(rows,list) or not isinstance(states,list)
        or len(rows)!=len(states) or len(rows)!=len(observations)):
        raise ValueError("P4 research and P3 historical identities are not one-to-one")
    by_name={}
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("invalid P4 screened issuer")
        issuer=row.get("issuer")
        if issuer in by_name:
            raise ValueError("duplicate P4 issuer")
        by_name[issuer]=row
    if set(by_name)!={x.get("issuer") for x in states}:
        raise ValueError("P4/P3 issuer set mismatch")
    blocked=[]
    for row in states:
        issuer=row.get("issuer")
        state=row.get("candidate_policy_research_state")
        if (state not in ALLOWED
            or row.get("candidate_approved") is not False
            or row.get("executable") is not False):
            raise ValueError("untrusted ST/halt research result")
        upstream=by_name[issuer]
        existing=upstream.get("category")
        if not isinstance(existing,str):
            raise ValueError("missing upstream research category")
        blocked.append({
            "issuer":issuer,
            "asof_completed_day":research["asof"],
            "upstream_dual_horizon_research_category":existing,
            "historical_risk_state":state,
            "dated_issuer_notice_veto":state in RISK,
            "final_research_candidate_category":"D_BLOCKED_HISTORICAL_ST_HALT_OR_UNKNOWN_PIT",
            "may_be_recommended_to_buy":False,
            "may_be_exported_to_execution":False,
            "research_label_overridden":True,
        })
    return {
        "phase":PHASE,
        "asof":research["asof"],
        "source_epoch_sha256":source["source_epoch_sha256"],
        "assessed_issuers":len(blocked),
        "dated_issuer_notice_veto_count":sum(x["dated_issuer_notice_veto"] for x in blocked),
        "research_labels_safety_blocked":len(blocked),
        "results":blocked,
        "all_research_candidates_blocked":True,
        "production_candidate_pipeline_integrated":False,
        "full_historical_PIT_ST_universe_verified":False,
        "historical_PIT_verified":False,
        "research_only":True,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
        "buy_recommendations_authorized":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--crosswalk",required=True,type=Path)
    p.add_argument("--research",required=True,type=Path)
    p.add_argument("--risk-samples",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=integrate(json.loads(a.crosswalk.read_text()),
                     json.loads(a.research.read_text()),
                     json.loads(a.risk_samples.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
       "phase":result["phase"],"assessed_issuers":result["assessed_issuers"],
       "historical_vetoed":result["dated_issuer_notice_veto_count"],
       "execution_candidates":0,"trade_gate":"BLOCKED"},sort_keys=True))
if __name__=="__main__":main()
