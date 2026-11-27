"""Pre-entry risk budget and conservative daily-bar exit research, never a fill model."""
import argparse,csv,json
from collections import Counter,defaultdict
from decimal import Decimal as D,ROUND_FLOOR
from pathlib import Path
from collector.p2_short_horizon_proxy import CAPITAL,SLIPPAGE,STAMP,commission
from collector.p2_refresh_batch_replay import checked_bytes
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between
from datetime import date

def pnl(buy,sell,qty):
    cost=buy*qty;proceeds=sell*qty
    return proceeds-cost-commission(cost)-commission(proceeds)-proceeds*STAMP

def budget(open_price):
    buy=open_price*(1+SLIPPAGE)
    stop=open_price*D(".98")
    target=open_price*D("1.05")
    lots=int((CAPITAL/(100*buy)).to_integral_value(rounding=ROUND_FLOOR))
    for n in range(lots,0,-1):
        q=n*100
        if buy*q+commission(buy*q)>CAPITAL:continue
        loss=-pnl(buy,stop*(1-SLIPPAGE),q)
        reward=pnl(buy,target*(1-SLIPPAGE),q)
        if loss<=0 or reward<2*loss or loss>CAPITAL*D(".03"):continue
        return q,buy,stop,target,loss,reward
    return None

def observe(day,bars,calendar):
    i=calendar.index(day)
    future=calendar[i+1:i+6]
    if not future:return dict(status="RIGHT_CENSORED")
    entry=bars.get(future[0])
    if not entry or entry["tradestatus"]!="1" or D(entry["volume"])<=0:return dict(status="ENTRY_UNAVAILABLE")
    if date.fromisoformat(future[0]).weekday()==4:return dict(status="FRIDAY_ENTRY_BLOCKED")
    b=budget(D(entry["open"]))
    if b is None:return dict(status="RISK_BUDGET_REJECTED")
    q,buy,stop,target,loss,reward=b
    def finish(day,price,reason):
        net=pnl(buy,price*(1-SLIPPAGE),q)
        return dict(status="PRICED_EXIT_PROXY",exit_reason=reason,entry_day=future[0],exit_day=day,shares=q,
                    planned_loss_cny=str(loss.quantize(D(".01"))),planned_reward_cny=str(reward.quantize(D(".01"))),
                    net_proxy_pnl_cny=str(net.quantize(D(".01"))),net_capital_return_pct=str((net/CAPITAL*100).quantize(D(".0001"))),
                    loss_budget_breached=net<-CAPITAL*D(".03"),execution_verified=False)
    for j,d in enumerate(future):
        row=bars.get(d)
        if not row or row["tradestatus"]!="1" or D(row["volume"])<=0:return dict(status="EXIT_WINDOW_UNAVAILABLE")
        if j==0:continue # T+1: no same-day sell, even if stop touched
        o,h,l,c=(D(row[k]) for k in ("open","high","low","close"))
        if o<=stop:return finish(d,o,"GAP_BELOW_STOP")
        if o>=target:return finish(d,o,"GAP_ABOVE_TARGET")
        if l<=stop and h>=target:return dict(status="AMBIGUOUS_DUAL_TOUCH")
        if l<=stop:return finish(d,stop,"STOP_TOUCH")
        if h>=target:return finish(d,target,"TARGET_TOUCH")
        if date.fromisoformat(d).weekday()==4:return finish(d,c,"FRIDAY_CLOSE")
        if j==4:return finish(d,c,"FIFTH_SESSION_CLOSE")
    return dict(status="RIGHT_CENSORED")

def run(manifest,root,packages,report,signal_report):
    for r in (report,signal_report):
        if r["trade_gate"]!="BLOCKED" or r["historical_PIT_verified"] is not False or r["orders"]!=[] or r["executable_candidates"]!=[]:raise ValueError("unsafe source")
    if report["target_asof"]!="2026-11-25" or report["accepted_issuers"]!=3194 or report["full_universe_observed"] is not True or signal_report["asof"]!="2026-11-25":raise ValueError("wrong scope")
    by={r["code"]:r for r in report["results"]};claimed=defaultdict(list)
    for r in signal_report["signals"]:claimed[r["code"]].append(r["signal_day"])
    if len(by)!=3194 or not set(claimed)<=set(by) or any(len(v)!=len(set(v)) for v in claimed.values()):raise ValueError("bad signal scope")
    calendar=sessions_between("2026-10-21","2026-11-25")
    details=[];seen=set()
    for batch in manifest["batches"]:
        for row in batch["issuers"]:
            code=row["code"]
            if code in seen:raise ValueError("duplicate issuer")
            seen.add(code)
            if code not in claimed:continue
            f=code.replace(".","_")+".csv"
            a=checked_bytes(root/row["source_shard"]/f,row["original_csv_sha256"])
            b=checked_bytes(packages/f"p2-batch-{batch['index']:04d}"/f,by[code]["extension_sha256"])
            audit_csv(a,code);audit_csv(b,code)
            bars={r["date"]:r for r in list(csv.DictReader(a.decode("utf-8-sig").splitlines()))+list(csv.DictReader(b.decode("utf-8-sig").splitlines()))}
            if max(bars)>"2026-11-25":raise ValueError("future bar")
            for day in claimed[code]:details.append(dict(code=code,signal_day=day,**observe(day,bars,calendar)))
    if seen!=set(by) or len(details)!=signal_report["signal_count"]:raise ValueError("incomplete scope")
    priced=[r for r in details if r["status"]=="PRICED_EXIT_PROXY"]
    net=[D(r["net_capital_return_pct"]) for r in priced]
    return dict(asof="2026-11-25",signal_count=len(details),status_counts=dict(Counter(r["status"] for r in details)),
                exit_reasons=dict(Counter(r["exit_reason"] for r in priced)),positive_proxy_count=sum(v>0 for v in net),
                mean_capital_proxy_pct=str((sum(net)/len(net)).quantize(D(".0001"))) if net else None,
                loss_budget_breaches=sum(r["loss_budget_breached"] for r in priced),
                risk_budget_basis="8000 CNY capital, planned net loss <=3%, modeled net reward/loss >=2",
                stop_target_basis="entry vendor open; 2%/5%; T+1; Friday entry blocked and Friday close exit; dual touches unresolved",
                daily_bar_intraday_sequence_verified=False,limit_band_verified=False,corporate_actions_verified=False,portfolio_simulated=False,
                execution_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],details=details)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("manifest","archive-epoch","packages","report","signal-report","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages,json.loads(a.report.read_bytes()),json.loads(a.signal_report.read_bytes()))
    a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_SHORT_RISK_PROXY:",json.dumps({k:v for k,v in r.items() if k!="details"}))
