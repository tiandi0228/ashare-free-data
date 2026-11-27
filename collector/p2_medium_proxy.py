"""Fixed medium-horizon retrospective vendor research, not execution or holdout."""
import argparse,csv,json
from collections import Counter
from decimal import Decimal as D,ROUND_FLOOR
from pathlib import Path
from collector.p2_refresh_batch_replay import checked_bytes
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between
from collector.p2_short_horizon_proxy import CAPITAL,SLIPPAGE,STAMP,commission

START="2026-07-01"
SIGNAL_END="2026-10-20"
END="2026-11-25"
HORIZONS=(20,40,60)

def medium_signals(rows,calendar):
    seen=set();result=[];positions={d:i for i,d in enumerate(calendar)}
    for i in range(60,len(rows)):
        day=rows[i]["date"]
        if day<START or day>SIGNAL_END or day[:7] in seen:continue
        w=rows[i-60:i+1];j=positions.get(day,-1)
        if j<60 or [r["date"] for r in w]!=calendar[j-60:j+1] or any(r["tradestatus"]!="1" for r in w):continue
        c=[D(r["close"]) for r in w];v=[D(r["volume"]) for r in w]
        if min(v)<=0:continue
        if sum(c[-21:-1])/20<=sum(c[:-1])/60 and sum(c[-20:])/20>sum(c[1:])/60 and c[-1]>sum(c[-20:])/20:
            result.append(day);seen.add(day[:7])
    return result

def observe(day,bars,calendar,h):
    if h not in HORIZONS:raise ValueError("invalid horizon")
    i=calendar.index(day)
    future=calendar[i+1:i+1+h]
    if len(future)!=h:return dict(status="RIGHT_CENSORED")
    if any(d not in bars for d in future):return dict(status="MISSING_VENDOR_SESSION")
    if any(bars[d]["tradestatus"]!="1" or D(bars[d]["volume"])<=0 for d in future):return dict(status="NONTRADABLE_WINDOW")
    buy=D(bars[future[0]]["open"])*(1+SLIPPAGE)
    sell=D(bars[future[-1]]["close"])*(1-SLIPPAGE)
    lots=int((CAPITAL/(buy*100)).to_integral_value(rounding=ROUND_FLOOR))
    while lots and buy*lots*100+commission(buy*lots*100)>CAPITAL:lots-=1
    if not lots:return dict(status="UNAFFORDABLE_BOARD_LOT")
    q=lots*100;cost=buy*q;proceeds=sell*q
    net=proceeds-cost-commission(cost)-commission(proceeds)-proceeds*STAMP
    return dict(status="PRICED_VENDOR_PROXY",entry_day=future[0],exit_day=future[-1],shares=q,net_capital_proxy_pct=str((net/CAPITAL*100).quantize(D(".0001"))),execution_verified=False)

def run(manifest,root,packages,report):
    if report["trade_gate"]!="BLOCKED" or report["orders"]!=[] or report["executable_candidates"]!=[] or report["historical_PIT_verified"] is not False or report["target_asof"]!=END or report["accepted_issuers"]!=3194 or report["full_universe_observed"] is not True:raise ValueError("unsafe scope")
    by={r["code"]:r for r in report["results"]}
    if len(by)!=3194:raise ValueError("duplicate issuer")
    calendar=sessions_between("2026-01-01",END)
    seen=set();details=[];signal_count=0;signal_issuers=set()
    for batch in manifest["batches"]:
        for row in batch["issuers"]:
            code=row["code"]
            if code in seen:raise ValueError("duplicate issuer")
            seen.add(code);f=code.replace(".","_")+".csv"
            a=checked_bytes(root/row["source_shard"]/f,row["original_csv_sha256"])
            b=checked_bytes(packages/f"p2-batch-{batch['index']:04d}"/f,by[code]["extension_sha256"])
            audit_csv(a,code);audit_csv(b,code)
            rows=list(csv.DictReader(a.decode("utf-8-sig").splitlines()))+list(csv.DictReader(b.decode("utf-8-sig").splitlines()))
            if rows[-1]["date"]>END:raise ValueError("future data")
            rows=[r for r in rows if r["date"]>="2026-01-01"]
            bars={r["date"]:r for r in rows}
            if len(bars)!=len(rows):raise ValueError("duplicate date")
            for day in medium_signals(rows,calendar):
                signal_count+=1;signal_issuers.add(code)
                for h in HORIZONS:details.append(dict(code=code,signal_day=day,horizon_sessions=h,**observe(day,bars,calendar,h)))
    if seen!=set(by) or len(details)!=signal_count*len(HORIZONS):raise ValueError("scope mismatch")
    summary={}
    for h in HORIZONS:
        items=[r for r in details if r["horizon_sessions"]==h]
        priced=[r for r in items if r["status"]=="PRICED_VENDOR_PROXY"]
        net=[D(r["net_capital_proxy_pct"]) for r in priced]
        summary[str(h)]=dict(observations=len(items),statuses=dict(Counter(r["status"] for r in items)),priced=len(priced),positive=sum(v>0 for v in net),mean_net_capital_proxy_pct=str((sum(net)/len(net)).quantize(D(".0001"))) if net else None)
    return dict(asof=END,signal_start=START,signal_end=SIGNAL_END,issuer_count=len(seen),signal_count=signal_count,signal_issuers=len(signal_issuers),strategy="MA20 crosses above MA60; close above MA20; first signal per issuer/month",summary=summary,holding_period="20/40/60 exchange sessions approximating 1/2/3 months",selected_strategy=None,corporate_actions_verified=False,sector_verified=False,portfolio_simulated=False,stop_target_simulated=False,independent_holdout_verified=False,execution_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],details=details)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("manifest","archive-epoch","packages","report","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages,json.loads(a.report.read_bytes()))
    a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_MEDIUM_PROXY:",json.dumps({k:v for k,v in r.items() if k!="details"}))
