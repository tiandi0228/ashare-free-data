"""Research-only fixed-horizon next-open/close proxies; not fills or realized P&L."""
import argparse,csv,json
from collections import Counter,defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
from collector.p2_refresh_batch_replay import checked_bytes
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between
from collector.p2_short_signal_replay import signals

D=Decimal
END="2026-11-25"
HORIZONS=(3,4,5)
CAPITAL=D("8000")
COMMISSION=D("0.0002854")
STAMP=D("0.0005")
SLIPPAGE=D("0.001")
MIN_FEE=D("5")

def commission(value):
    return max(MIN_FEE,value*COMMISSION)

def observe(day,bars,calendar,h):
    if h not in HORIZONS or day not in calendar:raise ValueError("bad horizon or day")
    i=calendar.index(day)
    future=calendar[i+1:i+1+h]
    if len(future)!=h:return dict(status="RIGHT_CENSORED")
    if any(d not in bars for d in future):return dict(status="MISSING_VENDOR_SESSION")
    if any(bars[d]["tradestatus"]!="1" for d in future):return dict(status="VENDOR_NONTRADABLE_WINDOW")
    if any(D(bars[d]["volume"])<=0 for d in future):return dict(status="ZERO_VOLUME_WINDOW")
    entry=D(bars[future[0]]["open"]);exit=D(bars[future[-1]]["close"])
    buy=entry*(1+SLIPPAGE);sell=exit*(1-SLIPPAGE)
    lots=int((CAPITAL/(100*buy)).to_integral_value(rounding=ROUND_FLOOR))
    while lots and buy*lots*100+commission(buy*lots*100)>CAPITAL:lots-=1
    if not lots:return dict(status="UNAFFORDABLE_BOARD_LOT")
    qty=lots*100;cost=buy*qty;proceeds=sell*qty
    fees=commission(cost)+commission(proceeds)+proceeds*STAMP
    pnl=proceeds-cost-fees
    return dict(status="PRICED_VENDOR_PROXY",entry_day=future[0],exit_day=future[-1],shares=qty,
                entry_open=str(entry),exit_close=str(exit),fee_proxy_cny=str(fees.quantize(D(".01"))),
                gross_return_pct=str(((exit/entry-1)*100).quantize(D(".0001"))),
                net_deployed_return_pct=str((pnl/(cost+commission(cost))*100).quantize(D(".0001"))),
                net_proxy_pnl_cny=str(pnl.quantize(D(".01"))),execution_verified=False)

def run(manifest,root,packages,report,signal_report):
    for r in (report,signal_report):
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["historical_PIT_verified"] is not False:raise ValueError("unsafe source")
    if report["accepted_issuers"]!=3194 or report["full_universe_observed"] is not True or report["target_asof"]!=END or signal_report["asof"]!=END:raise ValueError("wrong scope")
    by={r["code"]:r for r in report["results"]}
    claimed=defaultdict(list)
    for r in signal_report["signals"]:claimed[r["code"]].append(r)
    calendar=sessions_between("2026-10-21",END)
    details=[];scanned=set()
    for batch in manifest["batches"]:
        for row in batch["issuers"]:
            code=row["code"];f=code.replace(".","_")+".csv"
            if code in scanned:raise ValueError("duplicate issuer")
            scanned.add(code)
            a=checked_bytes(root/row["source_shard"]/f,row["original_csv_sha256"])
            b=checked_bytes(packages/f"p2-batch-{batch['index']:04d}"/f,by[code]["extension_sha256"])
            audit_csv(a,code);audit_csv(b,code)
            rows=list(csv.DictReader(a.decode("utf-8-sig").splitlines()))+list(csv.DictReader(b.decode("utf-8-sig").splitlines()))
            if rows[-1]["date"]>END:raise ValueError("future data")
            rebuilt=[r for r in signals([r for r in rows if r["date"]>="2026-09-01"],code) if "2026-10-21"<=r["signal_day"]<=END]
            if rebuilt!=claimed.get(code,[]):raise ValueError("signal mismatch")
            bars={r["date"]:r for r in rows}
            for sig in rebuilt:
                for h in HORIZONS:
                    details.append(dict(code=code,signal_day=sig["signal_day"],horizon_sessions=h,**observe(sig["signal_day"],bars,calendar,h)))
    if scanned!=set(by) or not set(claimed)<=scanned or len(details)!=signal_report["signal_count"]*len(HORIZONS):raise ValueError("incomplete scope")
    summary={}
    for h in HORIZONS:
        items=[r for r in details if r["horizon_sessions"]==h]
        priced=[r for r in items if r["status"]=="PRICED_VENDOR_PROXY"]
        net=[D(r["net_deployed_return_pct"]) for r in priced]
        summary[str(h)]=dict(status_counts=dict(Counter(r["status"] for r in items)),observations=len(items),
                             positive_net_proxy_count=sum(v>0 for v in net),mean_net_proxy_pct=str((sum(net)/len(net)).quantize(D(".0001"))) if net else None)
    return dict(asof=END,issuer_count=len(scanned),signal_count=signal_report["signal_count"],holding_period_convention="entry session counted as day 1; exit close of day N",capital_cny=str(CAPITAL),commission=str(COMMISSION),min_commission_cny=str(MIN_FEE),stamp_sell=str(STAMP),slippage_each_side=str(SLIPPAGE),summary=summary,portfolio_simulated=False,stop_target_simulated=False,friday_exit_simulated=False,corporate_actions_verified=False,limit_band_verified=False,execution_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],details=details)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("manifest","archive-epoch","packages","report","signal-report","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages,json.loads(a.report.read_bytes()),json.loads(a.signal_report.read_bytes()))
    a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_SHORT_HORIZON_PROXY:",json.dumps({k:v for k,v in r.items() if k!="details"}))
