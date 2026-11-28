"""Join frozen price proxies to vendor flat-bar hypotheses, never infer execution."""
import argparse,hashlib,json,re,zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from collector.p4_flat_bar_risk import SHA as FROZEN_SHA
from collector.p4_curated_session_exit import sessions_between

STRATEGY_SHA="22cf31fcd3a069ea0567f2d1c9f9a160bc6d06253b42ad45e0e02c90207d9d48"
ASOF="2026-11-25"
START="2026-10-22" # first extension session lacks prior close in this audit
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def safe(r):
    if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["historical_PIT_verified"] is not False:
        raise ValueError("unsafe research source")

def build_flags(risk,aggregate):
    safe(risk);safe(aggregate)
    if risk["source_artifact_sha256"]!=FROZEN_SHA or risk["asof"]!=ASOF or risk["issuer_count"]!=3194 or risk["official_limit_certified"]!=0 or risk["execution_verified"] is not False:
        raise ValueError("wrong risk scope")
    if aggregate["target_asof"]!=ASOF or aggregate["accepted_issuers"]!=3194 or aggregate["full_universe_observed"] is not True:
        raise ValueError("wrong aggregate scope")
    by={r["code"]:r["extension_sha256"] for r in aggregate["results"]}
    if len(by)!=3194:raise ValueError("duplicate issuer")
    flags={}
    matched=0
    for r in risk["records"]:
        k=(r["code"],r["day"])
        if k in flags or by.get(r["code"])!=r["extension_sha256"] or not START<=r["day"]<=ASOF:
            raise ValueError("wrong risk original or duplicate date")
        if r["official_limit_verified"] is not False or r["fill_verified"] is not False:
            raise ValueError("uncertified hypothesis required")
        sides=set()
        for h in r["hypotheses"]:
            if h["side"] not in ("UP","DOWN") or h["assumed_band_pct"] not in ("5.00","10.00"):raise ValueError("invalid hypothesis")
            sides.add(h["side"])
        flags[k]=sides
        matched+=bool(sides)
    if len(flags)!=risk["counts"]["flat_active_adjacent_observations"] or matched!=risk["counts"].get("hypothetical_band_matches",0):raise ValueError("risk count mismatch")
    return by,flags

def classify(row,flags):
    entry=row["entry_day"];exit=row["exit_day"];code=row["code"]
    if not START<=entry<exit<=ASOF or sessions_between(entry,exit)[0]!=entry or sessions_between(entry,exit)[-1]!=exit:
        raise ValueError("outside comparable T+1 window")
    up="UP" in flags.get((code,entry),set())
    down="DOWN" in flags.get((code,exit),set())
    days=sessions_between(entry,exit)
    other=[d for d in days if flags.get((code,d))]
    return dict(entry_up_hypothesis=up,exit_down_hypothesis=down,any_flagged_window_days=other,
                execution_status="POTENTIAL_DIRECTIONAL_LIMIT_RISK" if up or down else "NO_DIRECTIONAL_FLAG_NOT_FILL_PROOF",execution_verified=False)

def reconcile(rows,flags,universe,signals,horizon=False):
    keys=set();counts=Counter();details=[]
    for r in rows:
        key=(r["code"],r["signal_day"])
        if key not in signals or r["code"] not in universe:raise ValueError("unknown signal")
        if horizon:
            if r["horizon_sessions"] not in (3,4,5):raise ValueError("wrong horizon")
            key=(*key,r["horizon_sessions"])
        if key in keys:raise ValueError("duplicate observation")
        keys.add(key)
        counts["observations"]+=1
        if r["status"]!=("PRICED_VENDOR_PROXY" if horizon else "PRICED_EXIT_PROXY"):
            counts["not_priced"]+=1
            continue
        if r["execution_verified"] is not False or not r["signal_day"]<r["entry_day"]:raise ValueError("unsafe chronology")
        c=classify(r,flags)
        counts["priced"]+=1
        counts["entry_up_hypotheses"]+=c["entry_up_hypothesis"]
        counts["exit_down_hypotheses"]+=c["exit_down_hypothesis"]
        counts["directional_risk_observations"]+=c["entry_up_hypothesis"] or c["exit_down_hypothesis"]
        counts["any_window_hypothesis"]+=bool(c["any_flagged_window_days"])
        if c["any_flagged_window_days"]:
            details.append(dict(code=r["code"],signal_day=r["signal_day"],entry_day=r["entry_day"],exit_day=r["exit_day"],horizon_sessions=r.get("horizon_sessions"),**c))
    expected={(c,d,h) for c,d in signals for h in (3,4,5)} if horizon else signals
    if keys!=expected or counts["observations"]!=counts["priced"]+counts["not_priced"]:raise ValueError("incomplete signal denominator")
    for k in ("entry_up_hypotheses","exit_down_hypotheses","directional_risk_observations","any_window_hypothesis"):counts[k]+=0
    return dict(counts=counts,details=details)

def run(frozen,strategy,risk):
    if digest(frozen)!=FROZEN_SHA or digest(strategy)!=STRATEGY_SHA:raise ValueError("source artifact hash mismatch")
    with zipfile.ZipFile(frozen) as z,zipfile.ZipFile(strategy) as s:
        for archive in (z,s):
            names=archive.namelist()
            if len(names)!=len(set(names)):raise ValueError("duplicate ZIP members")
        a=json.loads(z.read("p2-refresh-aggregate.json"))
        b=json.loads(s.read("p2-refresh-aggregate.json"))
        if a!=b:raise ValueError("strategy source differs from frozen originals")
        sig=json.loads(s.read("p2-short-signal-replay.json"))
        horizons=json.loads(s.read("p2-short-horizon-proxy.json"))
        strata=json.loads(s.read("p2-short-trend-strata.json"))
    for r in (sig,horizons,strata):
        safe(r)
        if r["asof"]!=ASOF or r["signal_count"]!=3712:raise ValueError("wrong signal scope")
    signals={(r["code"],r["signal_day"]) for r in sig["signals"]}
    if len(signals)!=3712 or len(sig["signals"])!=3712:raise ValueError("duplicate signals")
    by,flags=build_flags(risk,a)
    fixed=reconcile(horizons["details"],flags,set(by),signals,True)
    variant=reconcile(strata["details"],flags,set(by),signals)
    return dict(asof=ASOF,source_artifact_sha256=FROZEN_SHA,strategy_artifact_sha256=STRATEGY_SHA,signal_count=len(signals),fixed_horizons=fixed,variant_a=variant,official_limit_certified=0,execution_verified=False,returns_recomputed=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("frozen","strategy","risk","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(a.frozen,a.strategy,json.loads(a.risk.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P4_PROXY_LIMIT_JOIN:",json.dumps({**r,"fixed_horizons":r["fixed_horizons"]["counts"],"variant_a":r["variant_a"]["counts"]}))
