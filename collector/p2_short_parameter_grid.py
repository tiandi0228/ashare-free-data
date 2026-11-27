"""Fixed retrospective sensitivity grid; no selection, deployment or out-of-sample claims."""
import argparse,json
from pathlib import Path
from decimal import Decimal as D
from collector.p2_short_risk_proxy import run
GRID=(("BASE","0.02","0.05"),("A","0.02","0.06"),("B","0.015","0.05"),("C","0.02","0.07"))

def compare(manifest,root,packages,report,signals,baseline):
    results=[]
    for name,s,t in GRID:
        r=run(manifest,root,packages,report,signals,D(s),D(t))
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["historical_PIT_verified"] is not False:raise ValueError("unsafe comparison")
        if r["signal_count"]!=signals["signal_count"] or sum(r["status_counts"].values())!=r["signal_count"]:raise ValueError("incomplete denominator")
        if name=="BASE" and r!=baseline:raise ValueError("frozen baseline changed")
        results.append(dict(variant=name,stop=s,target=t,**{k:v for k,v in r.items() if k!="details"}))
    return dict(asof="2026-11-25",purpose="retrospective sensitivity only",grid=results,selected_variant=None,
                independent_holdout_verified=False,execution_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("manifest","archive-epoch","packages","report","signal-report","baseline","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=compare(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages,json.loads(a.report.read_bytes()),json.loads(a.signal_report.read_bytes()),json.loads(a.baseline.read_bytes()))
    a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_SHORT_PARAMETER_GRID:",json.dumps(r))
