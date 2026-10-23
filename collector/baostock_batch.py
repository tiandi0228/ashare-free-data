"""Bounded Baostock historical source batches; independent public research only."""
import argparse,csv,hashlib,json,re,math
from pathlib import Path

FIELDS="date,code,open,high,low,close,volume,amount,adjustflag,tradestatus".split(",")
START,END="2024-10-20","2026-10-20"
CAP=8
PATTERN=re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")

def check_daily_bars(rows):
    """Reject impossible active OHLC bars; suspended placeholders remain non-executable."""
    active=0;suspended=0
    for row in rows:
        if row[9]=="0":
            suspended+=1
            continue
        if row[9]!="1":
            raise ValueError("Unknown trading status")
        try:
            o,h,l,close=(float(row[i]) for i in (2,3,4,5))
            volume=float(row[6]);amount=float(row[7])
        except (ValueError,TypeError) as exc:
            raise ValueError("Active bar has missing numeric prices") from exc
        if not all(math.isfinite(v) for v in (o,h,l,close,volume,amount)):
            raise ValueError("Active bar contains nonfinite numbers")
        if (min(o,h,l,close)<=0 or h<max(o,close,l) or
            l>min(o,close,h) or volume<0 or amount<0):
            raise ValueError("Active bar violates OHLC or quantity constraints")
        active+=1
    return active,suspended

def manifest(path):
    raw=Path(path).read_bytes()
    if len(raw)>32768: raise ValueError("Manifest oversized")
    codes=[x.strip() for x in raw.decode("utf-8-sig").splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if not 1<=len(codes)<=128 or len(codes)!=len(set(codes)) or any(not PATTERN.fullmatch(x) for x in codes):
        raise ValueError("Manifest must contain 1-128 unique mainboard identifiers")
    return codes,hashlib.sha256(raw).hexdigest()

def run(path,index,dest,bs):
    codes,source_sha=manifest(path)
    count=(len(codes)+CAP-1)//CAP
    if not 0<=index<count:raise ValueError("Invalid batch index")
    selected=codes[index*CAP:(index+1)*CAP]
    out=Path(dest);out.mkdir(parents=True,exist_ok=True)
    report={"phase":"BAOSTOCK_FREE_BOUNDED_BATCH","status":"BLOCKED_PARTIAL","batch_index":index,
      "manifest_sha256":source_sha,"batch_count":count,"issuer_count":len(selected),
      "login_attempts":1,"query_attempts":0,"results":[],"paid_api_calls":0,
      "official_exchange_authenticated":False,"historical_point_in_time_universe_verified":False,
      "historical_ST_halt_delist_verified":False,"full_market_history_verified":False,
      "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    logged=False
    try:
        print("P1_BATCH_LOGIN_START",flush=True)
        r=bs.login()
        print("P1_BATCH_LOGIN_RESULT",getattr(r,"error_code","UNKNOWN"),flush=True)
        if r.error_code!="0":raise ValueError("Login failed")
        logged=True
        for code in selected:
            item={"code":code,"status":"ERROR"}
            report["query_attempts"]+=1
            print("P1_BATCH_ISSUER_START",code,flush=True)
            try:
                q=bs.query_history_k_data_plus(code,fields=",".join(FIELDS),start_date=START,end_date=END,frequency="d",adjustflag="3")
                if q.error_code!="0" or list(q.fields)!=FIELDS:raise ValueError("Bad provider response")
                rows=[]
                while q.next():
                    row=q.get_row_data()
                    if len(row)!=len(FIELDS):raise ValueError("Malformed row")
                    rows.append(row)
                    if len(rows)>600:raise ValueError("Excessive rows")
                days=[row[0] for row in rows]
                if not days or days!=sorted(set(days)) or days[0]<START or days[-1]>END or any(row[1]!=code for row in rows):
                    raise ValueError("Date or identity mismatch")
                # Suspended sessions can appear as placeholder rows.
                # Preserve them but never count them as executable trading bars.
                statuses=[row[FIELDS.index("tradestatus")] for row in rows]
                if any(s not in ("0","1") for s in statuses):
                    raise ValueError("Unknown trading-status encoding")
                tradable,suspended=check_daily_bars(rows)
                raw=(",".join(FIELDS)+"\n"+"".join(",".join(row)+"\n" for row in rows)).encode()
                if len(raw)>250000:raise ValueError("Excessive source bytes")
                (out/(code.replace(".","_")+".csv")).write_bytes(raw)
                item.update(status="OBSERVED_UNVERIFIED",rows=len(rows),tradable_rows=tradable,suspended_status_rows=suspended,first=days[0],last=days[-1],sha256=hashlib.sha256(raw).hexdigest())
            except Exception as exc:
                item["error_type"]=type(exc).__name__
            report["results"].append(item)
            print("P1_BATCH_ISSUER_RESULT",code,item["status"],item.get("error_type",""),flush=True)
        if all(x["status"]=="OBSERVED_UNVERIFIED" for x in report["results"]):
            report["status"]="OBSERVED_SUBSET_UNVERIFIED"
    except Exception as exc:
        report["login_error_type"]=type(exc).__name__
    finally:
        if logged:
            try:bs.logout()
            except Exception:pass
        (out/"quality.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="OBSERVED_SUBSET_UNVERIFIED" else 2

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",default="manifests/baostock_pilot.txt")
    p.add_argument("--batch-index",type=int,required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    import baostock as bs
    raise SystemExit(run(args.manifest,args.batch_index,args.out,bs))
