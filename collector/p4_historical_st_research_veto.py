"""P4 research candidate historical ST/halt veto, NOT a brokerage gate.

Uses reviewed, source-linked P3 status event references and an exact set of
hypothetical as-of dates. No future OHLC or broker fills are read. The 600363
2026-09-29 halt and 2026-09-30 ST status are issuer-notice references,
not a fully authenticated point-in-time universe/state history.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

PHASE="P4_HISTORICAL_ST_HALT_RESEARCH_CANDIDATE_VETO"
CROSSWALK="P2_P3_FOUR_ISSUER_HALT_ST_CROSSWALK_RESEARCH_ONLY"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
MAINBOARD=re.compile(r"(?:sh\\.60[0-5]|sz\\.00[0-3])[0-9]{3}\\Z")

def classify(crosswalk, observations):
    if (not isinstance(crosswalk,dict)
        or crosswalk.get("phase")!=CROSSWALK
        or crosswalk.get("source_epoch_sha256")!=EPOCH
        or crosswalk.get("new_issuer_sources_linked")!=4
        or crosswalk.get("total_vendor_suspension_issuer_sources_linked")!=7
        or crosswalk.get("remaining_vendor_suspension_issuers_without_source_links")!=8
        or crosswalk.get("feature_complete_shards")!=226
        or crosswalk.get("feature_shards_promoted")!=0
        or crosswalk.get("issuer_source_pdf_bytes_sha_verified") is not False
        or crosswalk.get("historical_PIT_verified") is not False
        or crosswalk.get("trade_gate")!="BLOCKED"
        or crosswalk.get("orders")!=[]
        or crosswalk.get("executable_candidates")!=[]):
        raise ValueError("unsafe/unexpected P3 source crosswalk")
    warning=crosswalk.get("st_risk_exclusion")
    joined=crosswalk.get("issuer_results")
    if (not isinstance(warning,dict) or not isinstance(joined,dict)
        or set(joined)!={"sh.600363","sh.600825","sh.603159","sh.605303"}
        or warning.get("issuer")!="sh.600363"
        or warning.get("effective_from")!="2026-09-30"
        or warning.get("non_st_mainboard_screen_allowed_from_effective_day") is not False):
        raise ValueError("ST change or PIT lineage not present")
    issue=joined["sh.600363"]
    if (issue.get("curated_issuer_halt_start")!="2026-09-29"
        or issue.get("curated_issuer_resume_day")!="2026-09-30"
        or issue.get("risk_warning_st_effective_day")!="2026-09-30"
        or issue.get("issuer_notice_risk_name")!="ST联光"
        or issue.get("source_pdf_bytes_sha_verified") is not False
        or issue.get("gap_resolved") is not False):
        raise ValueError("ST issuer references inconsistent")
    if (not isinstance(observations,list) or not 1<=len(observations)<=100
        or any(not isinstance(x,dict) for x in observations)):
        raise ValueError("bounded synthetic P4 research observations required")
    results=[]
    seen=set()
    for record in observations:
        code=record.get("issuer")
        day=record.get("signal_known_after_close_date")
        if (not isinstance(code,str) or not MAINBOARD.fullmatch(code)
            or not isinstance(day,str)
            or record.get("research_only") is not True
            or record.get("buy_signal") is not False):
            raise ValueError("invalid or promotable test observation")
        try:
            parsed=date.fromisoformat(day)
        except ValueError as e:
            raise ValueError("noncanonical signal date") from e
        if parsed.isoformat()!=day or parsed.weekday()>=5:
            raise ValueError("noncanonical or weekend signal date")
        if (code,day) in seen:raise ValueError("duplicate symbol/date")
        seen.add((code,day))
        if code!="sh.600363":
            state="UNKNOWN_PIT_STATUS_FAIL_CLOSED"
        elif day=="2026-09-29":
            state="VETO_ISSUER_NOTICE_SUSPENDED_DAY"
        elif day>="2026-09-30":
            state="VETO_ISSUER_NOTICE_ST_EFFECTIVE"
        else:
            state="PRE_ST_NOTICE_INTERVAL_NOT_PIT_AUTHENTICATED"
        results.append({
            "issuer":code,"signal_known_after_close_date":day,
            "candidate_policy_research_state":state,
            "candidate_approved":False,
            "executable":False,
        })
    return {
        "phase":PHASE,"source_epoch_sha256":EPOCH,
        "asof_observations":len(results),"research_decisions":results,
        "st_effective_day":"2026-09-30",
        "halt_day":"2026-09-29",
        "research_exclusion_applied_to_600363":True,
        "policy_is_only_for_deterministic_research_replay":True,
        "production_trade_gate_implementation_verified":False,
        "historical_full_pit_states_verified":False,
        "source_pdf_original_bytes_verified":False,
        "historical_PIT_verified":False,
        "approved_entries":0,"orders":[],"executable_candidates":[],
        "trade_gate":"BLOCKED",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--crosswalk",required=True,type=Path)
    p.add_argument("--sample",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=classify(json.loads(a.crosswalk.read_text()),
                    json.loads(a.sample.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":result["phase"],
       "sample_count":result["asof_observations"],
       "vetoed_or_blocked":sum(not x["candidate_approved"] for x in result["research_decisions"]),
       "trade_gate":result["trade_gate"],"approved_entries":0}))
if __name__=="__main__":main()
