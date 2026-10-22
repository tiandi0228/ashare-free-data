"""Fresh Baostock roster observation, not a historical point-in-time certification."""
import argparse, hashlib, json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from collector.baostock_dated_universe import FIELDS, csv_bytes, inspect_rows

def capture(out, provider, day):
    path=Path(out)
    path.mkdir(parents=True, exist_ok=True)
    report={"phase":"P1_FRESH_VENDOR_ROSTER","requested_day":day,"status":"BLOCKED_PARTIAL",
            "observed_at_utc":datetime.now(ZoneInfo("UTC")).isoformat(),
            "source":"Baostock query_all_stock","logical_queries":0,"paid_api_calls":0,
            "historical_PIT_verified":False,"publisher_authenticated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    logged=False
    try:
        login=provider.login()
        if login.error_code!="0":
            raise ValueError("login failed")
        logged=True
        report["logical_queries"]=1
        q=provider.query_all_stock(day=day)
        if q.error_code!="0" or tuple(q.fields)!=FIELDS:
            raise ValueError("roster schema")
        rows=[]
        while q.next():
            rows.append(q.get_row_data())
            if len(rows)>10000:raise ValueError("roster excessive")
        main=inspect_rows(rows)
        raw=csv_bytes(main)
        (path/"mainboard.csv").write_bytes(raw)
        report.update(status="OBSERVED_UNVERIFIED",source_total_rows=len(rows),
                      mainboard_prefix_rows=len(main),mainboard_sha256=hashlib.sha256(raw).hexdigest(),
                      source_day_is_official_publication_proof=False)
    except Exception as exc:
        report["error_type"]=type(exc).__name__
        report["error_detail"]=str(exc)[:240]
    finally:
        if logged:
            try: provider.logout()
            except Exception: report["logout_error"]=True
        (path/"quality.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="OBSERVED_UNVERIFIED" else 2

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--day",default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    args=p.parse_args()
    import baostock
    raise SystemExit(capture(args.out,baostock,args.day))
if __name__=="__main__":
    main()
