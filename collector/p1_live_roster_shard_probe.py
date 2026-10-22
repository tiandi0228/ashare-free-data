"""Bounded free Baostock roster-to-bars discovery; retrospective research only."""
import argparse,csv,hashlib,json
from pathlib import Path
from collector.baostock_batch import run
from collector.p1_roster_shard_manifest import select_roster

def capture(out,bs,day="2026-10-20",batch_index=0):
    if type(batch_index) is not int or not 0<=batch_index<16:
        raise ValueError("batch index must be 0..15")
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    info={"phase":"P1_REAL_ROSTER_TO_EIGHT_BARS","date_requested":day,"trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"paid_api_calls":0,
          "historical_PIT_verified":False,"source_status":"ERROR"}
    logged=False
    try:
        login=bs.login()
        if login.error_code!="0":raise ValueError("roster login failed")
        logged=True
        q=bs.query_all_stock(day=day)
        if q.error_code!="0" or tuple(q.fields)!=("code","tradeStatus","code_name"):
            raise ValueError("unexpected roster schema")
        rows=[]
        while q.next():
            data=q.get_row_data()
            if len(data)!=3:raise ValueError("malformed roster row")
            rows.append({"code":data[0],"tradeStatus":data[1],"code_name":data[2]})
            if len(rows)>10000:raise ValueError("roster over cap")
        manifest,receipt=select_roster(rows,maximum=128)
        (root/"manifest.txt").write_text(manifest)
        info.update(roster_total=len(rows),mainboard_candidates=receipt["candidate_mainboard_count"],
                    shard_manifest_count=receipt["selected_count"],manifest_sha256=receipt["manifest_sha256"])
        # No nested second login: only a bounded first eight issuer observations.
        from collector.baostock_batch import FIELDS,START,END,check_daily_bars
        selected=manifest.splitlines()[batch_index*8:(batch_index+1)*8]
        info["batch_index"]=batch_index
        obtained=[]
        for code in selected:
            result=bs.query_history_k_data_plus(code,fields=",".join(FIELDS),
                    start_date=START,end_date=END,frequency="d",adjustflag="3")
            if result.error_code!="0" or list(result.fields)!=FIELDS:raise ValueError("bar schema")
            data=[]
            while result.next():
                row=result.get_row_data()
                if len(row)!=len(FIELDS):raise ValueError("bar fields")
                data.append(row)
                if len(data)>600:raise ValueError("too many bars")
            if not data:raise ValueError("empty bars")
            valid,suspended=check_daily_bars(data)
            if any(row[1]!=code for row in data):raise ValueError("issuer mismatch")
            raw=(",".join(FIELDS)+"\n"+"".join(",".join(row)+"\n" for row in data)).encode()
            name=code.replace(".","_")+".csv"
            (root/name).write_bytes(raw)
            obtained.append({"code":code,"rows":len(data),"valid_active_bars":valid,
                             "suspended_placeholder_rows":suspended,
                             "sha256":hashlib.sha256(raw).hexdigest()})
        info.update(source_status="EIGHT_FREE_ISSUER_HISTORIES_OBSERVED_RESEARCH_ONLY",
                    issuer_count=len(obtained),issuer_receipts=obtained)
    except Exception as exc:
        info.update(error_type=type(exc).__name__,error_message=str(exc)[:160])
    finally:
        if logged:
            try:bs.logout()
            except Exception:info["logout_failure"]=True
        (root/"quality.json").write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in info.items() if k!="issuer_receipts"},ensure_ascii=False))
    return 0 if info["source_status"]=="EIGHT_FREE_ISSUER_HISTORIES_OBSERVED_RESEARCH_ONLY" else 2
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    p.add_argument("--batch-index",type=int,default=0)
    a=p.parse_args()
    import baostock
    raise SystemExit(capture(a.out,baostock,batch_index=a.batch_index))
if __name__=="__main__":main()
