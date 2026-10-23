"""P2 vendor daily-bar integrity audit, explicitly not historical PIT certification."""
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path

FIELDS=["date","code","open","high","low","close","volume","amount","adjustflag","tradestatus"]

def audit_csv(raw,code):
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not rows or list(rows[0])!=FIELDS:raise ValueError("unexpected CSV schema")
    seen=set();active=0;suspended=0;last=None
    for row in rows:
        day=date.fromisoformat(row["date"])
        if row["code"]!=code or day in seen or (last is not None and day<=last):
            raise ValueError("repeated/out-of-order day or different issuer")
        seen.add(day);last=day
        if row["adjustflag"]!="3":raise ValueError("unexpected adjusted prices")
        if row["tradestatus"]=="0":
            suspended+=1
            continue
        if row["tradestatus"]!="1":raise ValueError("unknown vendor trade status")
        vals=[float(row[k]) for k in ("open","high","low","close","volume","amount")]
        if not all(math.isfinite(v) for v in vals):raise ValueError("nonfinite quote")
        o,h,l,c,v,a=vals
        if min(o,h,l,c)<=0 or l>min(o,c,h) or h<max(o,c,l) or min(v,a)<0:
            raise ValueError("invalid active OHLC")
        active+=1
    return {"active_rows":active,"vendor_suspended_rows":suspended,"total_rows":len(rows),
            "first":rows[0]["date"],"last":rows[-1]["date"]}

def assess(folder):
    folder=Path(folder)
    receipt=json.loads((folder/"quality.json").read_text())
    if receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or receipt.get("trade_gate")!="BLOCKED" or receipt.get("orders")!=[]:
        raise ValueError("unsafe or incomplete source receipt")
    if receipt.get("historical_point_in_time_universe_verified") is not False:
        raise ValueError("false vendor PIT certification")
    if receipt.get("issuer_count")!=len(receipt.get("results",[])):
        raise ValueError("incomplete receipt")
    details=[]
    for item in receipt["results"]:
        if item.get("status")!="OBSERVED_UNVERIFIED":raise ValueError("failed issuer")
        raw=(folder/(item["code"].replace(".","_")+".csv")).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item["sha256"]:raise ValueError("raw CSV hash mismatch")
        stats=audit_csv(raw,item["code"])
        if stats["total_rows"]!=item["rows"] or stats["active_rows"]!=item["tradable_rows"] or stats["vendor_suspended_rows"]!=item["suspended_status_rows"]:
            raise ValueError("receipt counts differ from CSV")
        details.append({"code":item["code"],**stats})
    return {"phase":"P2_INDEPENDENT_VENDOR_BAR_INTEGRITY",
            "issuer_count":len(details),"source_csv_sha_validated":True,
            "total_active_rows":sum(i["active_rows"] for i in details),
            "vendor_suspended_rows":sum(i["vendor_suspended_rows"] for i in details),
            "historical_PIT_verified":False,"official_halt_events_verified":False,
            "vendor_adjustment_verified":False,"trade_gate":"BLOCKED","orders":[],
            "executable_candidates":[],"details":details}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args()
    result=assess(a.input)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+chr(10))
    print(json.dumps({k:v for k,v in result.items() if k!="details"}))
if __name__=="__main__":main()
