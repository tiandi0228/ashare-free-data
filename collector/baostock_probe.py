"""One-issuer alternative source probe: independent Baostock protocol, not Eastmoney.

Exactly one login, one query, one logout. No retries, no fallback, no orders.
"""
import csv
import hashlib
import json
from pathlib import Path

CODE="sh.600000"
START="2024-10-20"
END="2026-10-20"
FIELDS="date,code,open,high,low,close,volume,amount,adjustflag,tradestatus".split(",")

def capture(out,bs):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    report={"source":"Baostock public service","status":"BLOCKED",
            "code":CODE,"login_attempts":0,"query_attempts":0,
            "underlying_http_calls_verified":False,"paid_api_calls":0,
            "publisher_identity_authenticated":False,"point_in_time_universe_verified":False,
            "market_wide_coverage_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
    logged=False
    try:
        report["login_attempts"]=1
        auth=bs.login()
        if auth.error_code!="0":
            raise ValueError("Login rejected")
        logged=True
        report["query_attempts"]=1
        result=bs.query_history_k_data_plus(CODE,fields=",".join(FIELDS),
            start_date=START,end_date=END,frequency="d",adjustflag="3")
        if result.error_code!="0" or list(result.fields)!=FIELDS:
            raise ValueError("Query schema or error_code mismatch")
        data=[]
        while result.next():
            values=result.get_row_data()
            if len(values)!=len(FIELDS):
                raise ValueError("Malformed row")
            data.append(values)
            if len(data)>600:
                raise ValueError("Response exceeds row budget")
        dates=[r[0] for r in data]
        if not dates or dates!=sorted(set(dates)) or dates[0]<START or dates[-1]>END:
            raise ValueError("No data or date ordering violated")
        if any(row[1]!=CODE for row in data):
            raise ValueError("Security code mismatch")
        p=out/"600000_baostock_original.csv"
        with p.open("w",encoding="utf-8",newline="") as f:
            writer=csv.writer(f);writer.writerow(FIELDS);writer.writerows(data)
        raw=p.read_bytes()
        if len(raw)>250000:
            p.unlink()
            raise ValueError("Byte budget exceeded")
        report.update(status="OBSERVED_UNVERIFIED",rows=len(data),
                      first=dates[0],last=dates[-1],sha256=hashlib.sha256(raw).hexdigest())
    except Exception as exc:
        report["error_type"]=type(exc).__name__
    finally:
        if logged:
            try: bs.logout()
            except Exception: pass
        (out/"quality.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="OBSERVED_UNVERIFIED" else 2

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    args=p.parse_args()
    import baostock as bs
    raise SystemExit(capture(args.out,bs))
