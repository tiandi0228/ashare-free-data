"""Bounded independent-provider three-issuer batch; research-only, one login session."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
from collector.baostock_probe import FIELDS,START,END

CODES=("sh.600000","sz.000001","sh.601398")
LIMIT=600

def collect(out,bs):
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    report={"phase":"FREE_BAOSTOCK_3_ISSUER_RESEARCH","provider":"Baostock",
            "codes":list(CODES),"login_attempts":1,"query_attempts":0,
            "issuer_results":[],"status":"BLOCKED",
            "official_exchange_authenticated":False,
            "historical_point_in_time_universe_verified":False,
            "historical_ST_halt_delist_verified":False,
            "full_market_history_verified":False,
            "paid_api_calls":0,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
    logged=False
    try:
        login=bs.login()
        if login.error_code!="0":
            raise ValueError("Provider login rejected")
        logged=True
        for code in CODES:
            item={"code":code,"status":"ERROR"}
            report["query_attempts"]+=1
            try:
                rs=bs.query_history_k_data_plus(code,fields=",".join(FIELDS),
                    start_date=START,end_date=END,frequency="d",adjustflag="3")
                if rs.error_code!="0" or list(rs.fields)!=FIELDS:
                    raise ValueError("Provider fields or response code invalid")
                lines=[]
                while rs.next():
                    row=rs.get_row_data()
                    if len(row)!=len(FIELDS): raise ValueError("Malformed provider row")
                    lines.append(row)
                    if len(lines)>LIMIT: raise ValueError("Oversized source result")
                dates=[r[0] for r in lines]
                if (not dates or dates!=sorted(set(dates)) or dates[0]<START or dates[-1]>END
                    or any(r[1]!=code for r in lines)):
                    raise ValueError("Source date/issuer validation failed")
                dest=root/(code.replace(".","_")+".csv")
                with dest.open("w",encoding="utf-8",newline="") as f:
                    writer=csv.writer(f);writer.writerow(FIELDS);writer.writerows(lines)
                raw=dest.read_bytes()
                if len(raw)>250000:
                    dest.unlink();raise ValueError("Byte budget exceeded")
                item.update(status="OBSERVED_UNVERIFIED",rows=len(lines),first=dates[0],
                    last=dates[-1],sha256=hashlib.sha256(raw).hexdigest())
            except Exception as exc:
                item["error_type"]=type(exc).__name__
            report["issuer_results"].append(item)
        if all(z["status"]=="OBSERVED_UNVERIFIED" for z in report["issuer_results"]):
            report["status"]="OBSERVED_3_ISSUERS_UNVERIFIED"
    except Exception as exc:
        report["login_error_type"]=type(exc).__name__
    finally:
        if logged:
            try:bs.logout()
            except Exception:pass
        (root/"quality.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="OBSERVED_3_ISSUERS_UNVERIFIED" else 2

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    args=p.parse_args()
    import baostock as bs
    raise SystemExit(collect(args.out,bs))
