"""Bounded retrospective vendor recovery check; no historical gap rewriting."""
import argparse,csv,hashlib,io,json,re
from datetime import date
from pathlib import Path
from collector.p2_independent_bars import FIELDS,audit_csv
from collector.p2_gap_recovery_plan import recovery
from collector.p4_curated_session_exit import sessions_between
from decimal import Decimal

START="2026-10-21"
END="2026-11-25"

def inspect(original,extension,code):
    old=audit_csv(original,code)
    if old["last"]!="2026-10-20":raise ValueError("unexpected historical cutoff")
    new=audit_csv(extension,code)
    if new["first"]<START or new["last"]>END:raise ValueError("extension outside bounded window")
    rows=list(csv.DictReader(original.decode("utf-8-sig").splitlines()))+list(csv.DictReader(extension.decode("utf-8-sig").splitlines()))
    r=recovery(rows,END)
    extension_days=[x['date'] for x in rows if x['date']>=START]
    expected=sessions_between(START,END)
    missing=sorted(set(expected)-set(extension_days))
    unexpected=sorted(set(extension_days)-set(expected))
    recent=rows[-21:]
    window_ok=(len(recent)==21 and [x['date'] for x in recent]==sessions_between(recent[0]['date'],END) and all(x['tradestatus']=='1' for x in recent))
    volume_ok=window_ok and sum(Decimal(x['volume']) for x in recent[:-1])>0
    complete=not missing and not unexpected
    eligible=complete and window_ok and volume_ok
    features=None
    if eligible:
        close=[Decimal(x['close']) for x in recent];volume=[Decimal(x['volume']) for x in recent]
        ma=sum(close[-20:])/20;high=max(close[-20:])
        features=dict(ma20_close_cny=str(ma.quantize(Decimal('0.0001'))),volume_vs_prior20_ratio=str((volume[-1]/(sum(volume[:-1])/20)).quantize(Decimal('0.0001'))),trailing20_close_drawdown_pct=str(((high-close[-1])/high*100).quantize(Decimal('0.0001'))))
    return dict(r,latest_observed_day=new["last"],new_vendor_rows=new["total_rows"],
                recovered_at_new_cutoff=eligible, expected_extension_sessions=len(expected),
                missing_expected_sessions=missing, unexpected_sessions=unexpected,
                curated_session_window_complete=window_ok, research_features=features,
                extension_sha256=hashlib.sha256(extension).hexdigest())

def run(plan,root,out,client):
    if plan["trade_gate"]!="BLOCKED" or plan["orders"]!=[] or plan["executable_candidates"]!=[] or plan["gap_issuers"]!=24 or len(plan["rows"])!=24:
        raise ValueError("unsafe or unexpected plan")
    codes=[r["issuer"] for r in plan["rows"]]
    if len(set(codes))!=24 or any(not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",c) for c in codes):
        raise ValueError("invalid issuer scope")
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    if client.login().error_code!="0":raise ValueError("provider login failed")
    try:
        for r in plan["rows"]:
            code=r["issuer"]
            folder=r["source_shard"]
            if not re.fullmatch(r"shard_[0-9]{4}",folder):raise ValueError("invalid shard")
            original=(root/folder/(code.replace(".","_")+".csv")).read_bytes()
            if hashlib.sha256(original).hexdigest()!=r["original_csv_sha256"]:raise ValueError("original hash mismatch")
            item=dict(issuer=code,original_csv_sha256=r["original_csv_sha256"],recovered_at_new_cutoff=False)
            try:
                q=client.query_history_k_data_plus(code,fields=",".join(FIELDS),start_date=START,end_date=END,frequency="d",adjustflag="3")
                if q.error_code!="0" or list(q.fields)!=FIELDS:raise ValueError("bad vendor response")
                rows=[]
                while q.next():
                    row=list(q.get_row_data())
                    if len(row)!=len(FIELDS) or not all(isinstance(x,str) for x in row):raise ValueError("bad row")
                    rows.append(row)
                    if len(rows)>36:raise ValueError("unbounded response")
                if q.error_code!="0" or not rows:raise ValueError("empty or partial vendor response")
                stream=io.StringIO(newline="")
                writer=csv.writer(stream,lineterminator="\n")
                writer.writerow(FIELDS);writer.writerows(rows)
                raw=stream.getvalue().encode()
                item.update(inspect(original,raw,code))
                filename=code.replace(".","_")+".csv"
                (out/filename).write_bytes(raw)
                item.update(status="VENDOR_EXTENSION_OBSERVED",filename=filename)
            except (ValueError,OSError,RuntimeError) as e:
                item.update(status="UNVERIFIED_EXTENSION",error=type(e).__name__)
            results.append(item)
    finally:client.logout()
    return dict(asof=END,issuer_count=len(results),new_cutoff_vendor_window_recovered=sum(x["recovered_at_new_cutoff"] for x in results),
                extension_calendar_complete=sum(x.get('missing_expected_sessions')==[] and x.get('unexpected_sessions')==[] for x in results),
                extensions_observed=sum(x["status"]=="VENDOR_EXTENSION_OBSERVED" for x in results),
                historical_gaps_resolved=0,official_sessions_verified=False,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[],results=results)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--plan",type=Path,required=True);p.add_argument("--archive-epoch",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    import baostock
    r=run(json.loads(a.plan.read_bytes()),a.archive_epoch,a.out,baostock)
    (a.out/"report.json").write_text(json.dumps(r,indent=2)+"\n")
    print("P2_EXTENSION_REPLAY:",json.dumps({k:v for k,v in r.items() if k!="results"}))
