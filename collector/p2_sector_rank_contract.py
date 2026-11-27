"""Fail-closed research sector ranking contract. No current industry backfill."""
import argparse,json,re
from datetime import date,datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
from collections import defaultdict

def rank(asof,universe,membership,returns):
    day=date.fromisoformat(asof)
    cutoff=datetime.fromisoformat(asof+"T15:00:00+08:00")
    if len(universe)!=len(set(universe)) or any(not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",c) for c in universe):raise ValueError("invalid universe")
    scope=set(universe);active={}
    for r in membership:
        if r["code"] not in scope:raise ValueError("out of scope membership")
        if not r.get("sector") or not re.fullmatch(r"[a-f0-9]{64}",r.get("source_sha256","")):raise ValueError("missing membership provenance")
        start=date.fromisoformat(r["effective_from"])
        end=date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None
        pub=datetime.fromisoformat(r["published_at"])
        if pub.tzinfo is None or (end is not None and end<=start):raise ValueError("invalid chronology")
        if r.get("publication_verified") is not True or pub>cutoff or start>day or (end is not None and day>=end):continue
        if r["code"] in active:raise ValueError("overlapping membership")
        active[r["code"]]=r["sector"]
    values={}
    for r in returns:
        code=r["code"]
        if code not in scope or code in values or r["asof"]!=asof:raise ValueError("invalid return scope")
        if r.get("window_verified") is not True:continue
        v=D(str(r["return20_pct"]))
        if not v.is_finite():raise ValueError("nonfinite return")
        values[code]=v
    common=set(active)&set(values)
    missing=sorted(scope-common)
    result=dict(asof=asof,universe_issuers=len(scope),membership_covered=len(active),return_covered=len(values),joint_covered=len(common),missing_codes=missing,sector_rankings=[],research_top3=[],macro_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])
    if missing or not scope:
        return dict(result,status="BLOCKED_INCOMPLETE_RESEARCH_INPUT")
    groups=defaultdict(list)
    for c in sorted(common):groups[active[c]].append((c,values[c]))
    eligible=[]
    for sector,rows in groups.items():
        if len(rows)<3:continue
        mean=sum(v for c,v in rows)/len(rows)
        eligible.append((sector,mean,rows))
    eligible.sort(key=lambda x:(-x[1],x[0]))
    for idx,(sector,mean,rows) in enumerate(eligible,1):
        result["sector_rankings"].append(dict(sector=sector,rank=idx,issuer_count=len(rows),mean_return20_pct=str(mean.quantize(D(".0001")))))
        top=sorted(rows,key=lambda x:(-x[1],x[0]))[:3]
        result["research_top3"].extend(dict(sector=sector,code=c,rank=i,return20_pct=str(v)) for i,(c,v) in enumerate(top,1))
    return dict(result,status="RESEARCH_ONLY_UNCERTIFIED_INPUT" if eligible else "BLOCKED_NO_ELIGIBLE_SECTOR")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();x=json.loads(a.input.read_bytes());r=rank(x["asof"],x["universe"],x["membership"],x["returns"])
    a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_SECTOR_CONTRACT:",json.dumps({k:v for k,v in r.items() if k!="missing_codes"}))
