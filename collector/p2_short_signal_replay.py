"""Frozen short-horizon research signals, not executable recommendations."""
import argparse,csv,json
from decimal import Decimal
from pathlib import Path
from collector.p2_refresh_batch_replay import checked_bytes
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between

def signals(rows,code):
    out=[]
    for i in range(20,len(rows)):
        w=rows[i-20:i+1]
        if [r["date"] for r in w]!=sessions_between(w[0]["date"],w[-1]["date"]) or any(r["tradestatus"]!="1" for r in w):continue
        c=[Decimal(r["close"]) for r in w]
        if c[-2]<=sum(c[:-1])/20 and c[-1]>sum(c[1:])/20:
            out.append(dict(code=code,signal_day=w[-1]["date"],close=str(c[-1]),signal="MA20_CROSS_UP",execution_verified=False))
    return out

def run(manifest,root,packages,report):
    if report["trade_gate"]!="BLOCKED" or report["historical_PIT_verified"] is not False or report["orders"]!=[] or report["executable_candidates"]!=[] or report["full_universe_observed"] is not True or report["accepted_issuers"]!=3194:raise ValueError("unsafe incomplete input")
    by={r["code"]:r for r in report["results"]}
    if len(by)!=3194:raise ValueError("wrong universe")
    result=[];count=0
    for batch in manifest["batches"]:
        for row in batch["issuers"]:
            code=row["code"];f=code.replace(".","_")+".csv"
            a=checked_bytes(root/row["source_shard"]/f,row["original_csv_sha256"])
            b=checked_bytes(packages/f"p2-batch-{batch['index']:04d}"/f,by[code]["extension_sha256"])
            audit_csv(a,code);audit_csv(b,code)
            rows=list(csv.DictReader(a.decode("utf-8-sig").splitlines()))+list(csv.DictReader(b.decode("utf-8-sig").splitlines()))
            if rows[-1]["date"]>"2026-11-25":raise ValueError("future data")
            # The fixed extension only is the evaluation interval; older rows supply lookback.
            result.extend(signals([r for r in rows if r["date"]>="2026-09-01"],code))
            count+=1
    result=[r for r in result if "2026-10-21"<=r["signal_day"]<="2026-11-25"]
    return dict(asof="2026-11-25",issuer_count=count,signal_count=len(result),signal_issuers=len({r["code"] for r in result}),strategy="MA20_CROSS_UP_RESEARCH",holding_period_validated=False,returns_verified=False,sector_filter_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],signals=result)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("manifest","archive-epoch","packages","report","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages,json.loads(a.report.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P2_SHORT_SIGNAL_REPLAY:",json.dumps({k:v for k,v in r.items() if k!="signals"}))
