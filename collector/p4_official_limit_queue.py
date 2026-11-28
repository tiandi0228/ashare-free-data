"""Prioritize official limit evidence by unique issuer/date, not proxy row count."""
import argparse,json,re
from collections import Counter
from pathlib import Path

def build(risk,join):
    for r in (risk,join):
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["historical_PIT_verified"] is not False or r["official_limit_certified"]!=0:raise ValueError("unsafe source")
    if risk["source_artifact_sha256"]!=join["source_artifact_sha256"] or risk["asof"]!=join["asof"] or risk["asof"]!="2026-11-25":raise ValueError("source mismatch")
    tasks={}
    for r in risk["records"]:
        if not r["hypotheses"]:continue
        key=(r["code"],r["day"])
        if key in tasks or not re.fullmatch(r"[a-f0-9]{64}",r["extension_sha256"]):raise ValueError("duplicate or invalid source")
        tasks[key]=dict(code=r["code"],day=r["day"],prior_day=r["prior_day"],extension_sha256=r["extension_sha256"],hypotheses=r["hypotheses"],entry_exposure=0,exit_exposure=0,window_exposure=0,official_limit_verified=False,required_evidence=["security_specific_official_reference_price","effective_ST_and_listing_status","applicable_limit_rule_version","corporate_action_reference_price","first_publication_and_effective_timestamp"])
    if len(tasks)!=risk["counts"]["hypothetical_band_matches"]:raise ValueError("wrong task denominator")
    for group in ("fixed_horizons","variant_a"):
        counts=Counter();seen=set()
        for row in join[group]["details"]:
            key=(row["code"],row["signal_day"],row["horizon_sessions"])
            if key in seen:raise ValueError("duplicate strategy row")
            seen.add(key)
            days=row["any_flagged_window_days"]
            if len(days)!=len(set(days)):raise ValueError("duplicate dates")
            counts["window"]+=bool(days)
            for day in days:
                tasks[(row["code"],day)]["window_exposure"]+=1
            for flag,dayfield,field,side in (("entry_up_hypothesis","entry_day","entry_exposure","UP"),("exit_down_hypothesis","exit_day","exit_exposure","DOWN")):
                if row[flag]:
                    t=tasks[(row["code"],row[dayfield])]
                    if side not in {h["side"] for h in t["hypotheses"]}:raise ValueError("direction mismatch")
                    t[field]+=1;counts[field]+=1
            counts["directional"]+=row["entry_up_hypothesis"] or row["exit_down_hypothesis"]
        expected=join[group]["counts"]
        for a,b in (("window","any_window_hypothesis"),("entry_exposure","entry_up_hypotheses"),("exit_exposure","exit_down_hypotheses"),("directional","directional_risk_observations")):
            if counts[a]!=expected[b]:raise ValueError("strategy exposure mismatch")
    for t in tasks.values():
        t["priority"]="P1_DIRECTIONAL" if t["entry_exposure"] or t["exit_exposure"] else "P2_WINDOW" if t["window_exposure"] else "P3_OTHER"
    ordered=sorted(tasks.values(),key=lambda t:(t["priority"],-(t["entry_exposure"]+t["exit_exposure"]),-t["window_exposure"],t["code"],t["day"]))
    return dict(asof=risk["asof"],source_artifact_sha256=risk["source_artifact_sha256"],unique_issuer_dates=len(ordered),unique_issuers=len({t["code"] for t in ordered}),priority_counts=dict(Counter(t["priority"] for t in ordered)),official_limit_certified=0,execution_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],tasks=ordered)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("risk","join","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=build(json.loads(a.risk.read_bytes()),json.loads(a.join.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_OFFICIAL_LIMIT_QUEUE:",json.dumps({k:v for k,v in r.items() if k!="tasks"}))
