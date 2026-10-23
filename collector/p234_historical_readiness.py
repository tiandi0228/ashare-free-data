"""P2/P4 independent historical research readiness gate, no trade authorization.

This checker never infers historical PIT state from current vendor rosters.
It is intentionally strict: unknown effective-time provenance always blocks OOS.
"""
import argparse,json
from pathlib import Path

REQUIREMENTS=(
    "historical_listing_membership",
    "historical_st_daily_state",
    "historical_halt_daily_state",
    "historical_delist_effective_state",
    "original_publication_timestamp",
    "source_redistribution_and_retention_rights",
    "frozen_out_of_sample_split",
    "cost_slippage_tplus1_replay",
)

def assess(evidence):
    if not isinstance(evidence,dict):raise ValueError("evidence must be a mapping")
    if evidence.get("trade_gate")!="BLOCKED" or evidence.get("orders")!=[]:
        raise ValueError("upstream trade boundary violated")
    checks={}
    for field in REQUIREMENTS:
        item=evidence.get(field)
        checks[field]=(isinstance(item,dict) and item.get("verified") is True
                       and item.get("scope")=="HISTORICAL_POINT_IN_TIME"
                       and isinstance(item.get("original_source_sha256"),str)
                       and len(item["original_source_sha256"])==64
                       and isinstance(item.get("audit_id"),str) and bool(item["audit_id"]))
    missing=[k for k,v in checks.items() if not v]
    return {"phase":"P2_P3_P4_HISTORICAL_READINESS",
            "requirements":checks,"missing_requirements":missing,
            "requirements_met":len(missing)==0,
            "historical_strategy_validated":False,
            "permission_to_trade":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--evidence",required=True);parser.add_argument("--out",required=True)
    args=parser.parse_args()
    result=assess(json.loads(Path(args.evidence).read_text()))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+chr(10))
    print(json.dumps(result))
if __name__=="__main__":main()
