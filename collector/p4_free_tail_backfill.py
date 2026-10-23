"""Bounded free Baostock attempt to recover source-tail exit dates; never merge unaudited data."""
import argparse,csv,hashlib,json
from datetime import date
from pathlib import Path
from collector.p4_real_exit_availability import audit
from collector.baostock_batch import FIELDS,check_daily_bars

def run(root,out,bs,limit=8):
    if not 1<=limit<=8:raise ValueError("bounded 1-8 issuers per run")
    source=audit(root)
    tasks=source["tail_backfill_requests"][:limit]
    output=Path(out);output.mkdir(parents=True,exist_ok=True)
    report={"phase":"P4_FREE_TAIL_BACKFILL_ATTEMPT","requested_issuers":len(tasks),
            "total_pending_issuers":source["tail_backfill_issuer_count"],
            "source_missing_exit_observations":source["missing_beyond_source_end"],
            "results":[],"successful_issuers":0,"recovered_target_rows":0,
            "source_archive_unchanged":True,"historical_PIT_verified":False,
            "official_halt_verified":False,"trade_gate":"BLOCKED","orders":[]}
    logged=False
    try:
        login=bs.login()
        if login.error_code!="0":raise ValueError("Baostock login error")
        logged=True
        for task in tasks:
            entry={"code":task["code"],"requested_start":task["earliest_missing_target"],
                   "requested_end":task["latest_missing_target"],"status":"SOURCE_UNAVAILABLE"}
            try:
                q=bs.query_history_k_data_plus(task["code"],fields=",".join(FIELDS),
                    start_date=task["earliest_missing_target"],end_date=task["latest_missing_target"],
                    frequency="d",adjustflag="3")
                if q.error_code!="0" or list(q.fields)!=FIELDS:raise ValueError("provider response error")
                rows=[]
                while q.next():
                    row=q.get_row_data()
                    if len(row)!=len(FIELDS):raise ValueError("malformed row")
                    rows.append(row)
                    if len(rows)>80:raise ValueError("unbounded result")
                dates=[row[0] for row in rows]
                if not rows or dates!=sorted(set(dates)) or any(row[1]!=task["code"] for row in rows):
                    raise ValueError("no valid vendor history")
                if dates[0]<task["earliest_missing_target"] or dates[-1]>task["latest_missing_target"]:
                    raise ValueError("provider result outside requested dates")
                active,suspended=check_daily_bars(rows)
                raw=(",".join(FIELDS)+"\n"+"".join(",".join(row)+"\n" for row in rows)).encode()
                filename=task["code"].replace(".","_")+"_tail.csv"
                (output/filename).write_bytes(raw)
                entry.update(status="OBSERVED_RESEARCH_ONLY",rows=len(rows),active=active,
                             vendor_suspended=suspended,sha256=hashlib.sha256(raw).hexdigest(),filename=filename)
                report["successful_issuers"]+=1;report["recovered_target_rows"]+=len(rows)
            except Exception as exc:entry["error_type"]=type(exc).__name__
            report["results"].append(entry)
    except Exception as exc:report["login_error_type"]=type(exc).__name__
    finally:
        if logged:
            try:bs.logout()
            except Exception:pass
    (output/"backfill_attempt.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=8);a=p.parse_args()
    import baostock as bs
    r=run(a.root,a.out,bs,a.limit)
    print(json.dumps({k:v for k,v in r.items() if k!="results"},ensure_ascii=False))
if __name__=="__main__":main()
