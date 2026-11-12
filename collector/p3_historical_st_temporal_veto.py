"""Historical as-of policy: no retroactive ST removal or disputed halt approval.

This policy is research-only and ALWAYS vetoes trade eligibility. The
date-specific reason can be used in offline audit, never to place orders.
It refuses applying 2026-10-20 ST-removal announcements to older days.
"""
import argparse,json,re
from pathlib import Path
from datetime import date

EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
PHASE="P3_HISTORICAL_ST_AND_CONFLICTED_HALT_EFFECTIVE_DAY_VETO"

def temporal_veto(manifest,issuer,asof_day):
    if (not isinstance(manifest,dict)
        or manifest.get("phase")!="P3_EIGHT_PREVIOUSLY_UNLINKED_ISSUER_DATED_DISCLOSURE_RESEARCH_V1"
        or manifest.get("source_epoch_sha256")!=EPOCH
        or manifest.get("historical_PIT_verified") is not False
        or manifest.get("trade_gate")!="BLOCKED"):
        raise ValueError("untrusted source temporal policy")
    if not isinstance(asof_day,str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}",asof_day):
        raise ValueError("invalid as-of day")
    asof=date.fromisoformat(asof_day)
    cases=[x for x in manifest.get("cases",[]) if x.get("issuer")==issuer]
    if len(cases)!=1:
        raise ValueError("no unique issuer source")
    case=cases[0]
    effective=case.get("st_removal_effective_day")
    if issuer=="sh.601238" and asof_day in ("2026-09-14","2026-09-15"):
        why="DISPUTED_2026_SEPTEMBER_HALT_START_NOT_EXCHANGE_VERIFIED"
    elif effective is not None:
        day=date.fromisoformat(effective)
        if asof<day:
            why="HISTORICAL_ST_BEFORE_RESEARCHED_REMOVAL_DAY"
        else:
            why="POST_ST_REMOVAL_DAY_STILL_NEEDS_INDEPENDENT_EXCHANGE_PIT"
    else:
        why="NO_INDEPENDENT_EXCHANGE_PIT_SESSION_PROOF"
    return {
        "phase":PHASE,"source_epoch_sha256":EPOCH,
        "issuer":issuer,"asof_day":asof_day,
        "known_historical_st_removal_research_day":effective,
        "reference_original_csv_sha256":case["original_csv_sha256"],
        "decision":"BLOCK","reason":why,
        "may_use_halt_calendar_as_approved_feature":False,
        "may_include_in_historical_non_ST_trade_universe":False,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    manifest=json.loads(a.manifest.read_text())
    examples=[
      ("sh.601238","2026-09-14"),
      ("sh.601238","2026-09-15"),
      ("sh.603517","2026-10-19"),
      ("sh.603517","2026-10-20"),
      ("sh.603838","2026-10-19"),
      ("sh.603838","2026-10-20"),
    ]
    out={"phase":PHASE,"historical_examples":[temporal_veto(manifest,*p) for p in examples],
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[]}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("P3_TEMPORAL_ST_DATE_VETO",json.dumps({
        "scenarios":len(out["historical_examples"]),
        "all_blocked":all(x["decision"]=="BLOCK" for x in out["historical_examples"]),
        "trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
