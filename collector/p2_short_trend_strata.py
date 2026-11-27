"""Fixed retrospective trend/volume strata; no selection or deployment."""
import argparse,csv,json
from collections import Counter,defaultdict
from decimal import Decimal as D
from pathlib import Path
from collector.p2_refresh_batch_replay import checked_bytes
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between
from collector.p2_short_signal_replay import signals
from collector.p2_short_risk_proxy import observe

def classify(rows,day):
    past=[r for r in rows if r["date"]<=day][-60:]
    if len(past)!=60 or past[-1]["date"]!=day or [r["date"] for r in past]!=sessions_between(past[0]["date"],day) or any(r["tradestatus"]!="1" for r in past):
        return "WINDOW_UNAVAILABLE"
    c=[D(r["close"]) for r in past];v=[D(r["volume"]) for r in past]
    prior=sum(v[-21:-1])
    if prior<=0:return "WINDOW_UNAVAILABLE"
    trend=c[-1]>sum(c[-20:])/20>sum(c)/60
    volume=v[-1]*20>=prior*D("1.5")
    return ("TREND" if trend else "NO_TREND")+("_VOLUME" if volume else "_NO_VOLUME")

def run(manifest,root,packages,report,signal_report):
    for r in (report,signal_report):
        if r["trade_gate"]!="BLOCKED" or r["historical_PIT_verified"] is not False or r["orders"]!=[] or r["executable_candidates"]!=[]:raise ValueError("unsafe input")
    if report["accepted_issuers"]!=3194 or report["full_universe_observed"] is not True or report["target_asof"]!="2026-11-25" or signal_report["asof"]!="2026-11-25":raise ValueError("wrong scope")
    by={r["code"]:r for r in report["results"]};claimed=defaultdict(list)
    for r in signal_report["signals"]:claimed[r["code"]].append(r)
    if len(by)!=3194:raise ValueError("duplicate issuer")
    cal=sessions_between("2026-10-21","2026-11-25")
    seen=set();details=[]
    for batch in manifest["batches"]:
        for row in batch["issuers"]:
            c=row["code"]
            if c in seen:raise ValueError("duplicate issuer")
            seen.add(c)
            f=c.replace(".","_")+".csv"
            a=checked_bytes(root/row["source_shard"]/f,row["original_csv_sha256"])
            b=checked_bytes(packages/f"p2-batch-{batch['index']:04d}"/f,by[c]["extension_sha256"])
            audit_csv(a,c);audit_csv(b,c)
            rows=list(csv.DictReader(a.decode("utf-8-sig").splitlines()))+list(csv.DictReader(b.decode("utf-8-sig").splitlines()))
            if rows[-1]["date"]>"2026-11-25":raise ValueError("future bars")
            rebuilt=[r for r in signals([r for r in rows if r["date"]>="2026-09-01"],c) if "2026-10-21"<=r["signal_day"]<="2026-11-25"]
            if rebuilt!=claimed.get(c,[]):raise ValueError("signal mismatch")
            bars={r["date"]:r for r in rows}
            for sig in rebuilt:
                day=sig["signal_day"];group=classify(rows,day)
                details.append(dict(code=c,signal_day=day,stratum=group,**observe(day,bars,cal,D(".02"),D(".06"))))
    if seen!=set(by) or not set(claimed)<=seen or len(details)!=signal_report["signal_count"]:raise ValueError("scope mismatch")
    summary={}
    for group in ("TREND_VOLUME","TREND_NO_VOLUME","NO_TREND_VOLUME","NO_TREND_NO_VOLUME","WINDOW_UNAVAILABLE"):
        items=[r for r in details if r["stratum"]==group]
        priced=[r for r in items if r["status"]=="PRICED_EXIT_PROXY"]
        net=[D(r["net_capital_return_pct"]) for r in priced]
        summary[group]=dict(signals=len(items),statuses=dict(Counter(r["status"] for r in items)),priced=len(priced),positive=sum(v>0 for v in net),mean_proxy_pct=str((sum(net)/len(net)).quantize(D(".0001"))) if net else None,loss_budget_breaches=sum(r["loss_budget_breached"] for r in priced))
    return dict(asof="2026-11-25",signal_count=len(details),summary=summary,trend="close > MA20 > MA60",volume="signal volume >= 1.5 times prior 20 session mean",parameter_variant="A fixed exploratory comparator, not selected",selected_stratum=None,independent_holdout_verified=False,sector_verified=False,execution_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],details=details)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("manifest","archive-epoch","packages","report","signal-report","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages,json.loads(a.report.read_bytes()),json.loads(a.signal_report.read_bytes()))
    a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_SHORT_TREND_STRATA:",json.dumps({k:v for k,v in r.items() if k!="details"}))
