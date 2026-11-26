"""Bounded retrospective vendor recovery check; no historical gap rewriting."""
import argparse,csv,hashlib,io,json,re
from datetime import date
from pathlib import Path
from collector.p2_independent_bars import FIELDS,audit_csv
from collector.p2_gap_recovery_plan import recovery

START="2026-10-21"
END="2026-11-25"

def inspect(original,extension,code):
    old=audit_csv(original,code)
    if old["last"]!="2026-10-20":raise ValueError("unexpected historical cutoff")
    new=audit_csv(extension,code)
    if new["first"]<START or new["last"]>END:raise ValueError("extension outside bounded window")
    rows=list(csv.DictReader(original.decode("utf-8-sig").splitlines()))+list(csv.DictReader(extension.decode("utf-8-sig").splitlines()))
    r=recovery(rows,END)
    return dict(r,latest_observed_day=new["last"],new_vendor_rows=new["total_rows"],
                recovered_at_new_cutoff=new["last"]==END and r["additional_consecutive_observations_needed"]==0,
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
