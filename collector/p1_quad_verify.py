"""Independent P1 source replay for up to four immutable historical CSV shards.

A matching SHA proves bytes were retained, not that the provider data is valid.
Validate date/issuer/fields/OHLC/status again before crediting durable coverage.
This is vendor consistency auditing, NEVER official PIT authentication.
"""
import argparse,csv,hashlib,io,json
from datetime import date
from pathlib import Path
from collector.baostock_batch import FIELDS,START,END,check_daily_bars

def _csv_replay(raw,code,source):
    if not raw or len(raw)>250000:
        raise ValueError("empty or oversized CSV")
    try:
        decoded=raw.decode("utf-8")
        reader=csv.reader(io.StringIO(decoded,newline=""))
        header=next(reader)
        rows=list(reader)
    except (UnicodeError,csv.Error,StopIteration) as exc:
        raise ValueError("invalid CSV bytes") from exc
    if header!=FIELDS or not 1<=len(rows)<=600:
        raise ValueError("wrong field order or bar count")
    if any(len(row)!=len(FIELDS) or row[1]!=code for row in rows):
        raise ValueError("wrong issuer or malformed bar")
    days=[row[0] for row in rows]
    try:
        validated=[date.fromisoformat(s) for s in days]
    except ValueError as exc:
        raise ValueError("invalid source date") from exc
    if (validated!=sorted(set(validated))
        or days[0]<START or days[-1]>END):
        raise ValueError("out-of-range or unsorted historical days")
    active,suspended=check_daily_bars(rows)
    if (type(source.get("rows")) is not int or source["rows"]!=len(rows)
        or source.get("first")!=days[0] or source.get("last")!=days[-1]
        or type(source.get("tradable_rows")) is not int or source["tradable_rows"]!=active
        or type(source.get("suspended_status_rows")) is not int
        or source["suspended_status_rows"]!=suspended):
        raise ValueError("provider metadata contradicts original CSV")
    return active,suspended

def verify(plan,items,manifest_root):
    if (plan.get("phase")!="P1_FRESH_VENDOR_SHARD_PLAN"
        or plan.get("trade_gate")!="BLOCKED"
        or plan.get("historical_PIT_verified") is not False):
        raise ValueError("unsafe roster plan")
    if not isinstance(items,list) or not 1<=len(items)<=4 or len(set(i for i,_ in items))!=len(items):
        raise ValueError("invalid distinct shard count")
    if (type(plan.get("shard_count")) is not int
        or len(plan.get("shards",[]))!=plan["shard_count"]):
        raise ValueError("inconsistent roster plan")
    codes=set();total=0;active_rows=0;suspended_rows=0
    for index,folder in items:
        if type(index)!=int or not 0<=index<plan["shard_count"]:
            raise ValueError("out-of-range index")
        expected=plan["shards"][index]
        if expected.get("index")!=index or not 1<=expected["count"]<=8:
            raise ValueError("invalid planned shard")
        manifest=Path(manifest_root)/expected["name"]
        raw=manifest.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected["sha256"]:
            raise ValueError("manifest digest")
        intended=[line.strip() for line in raw.decode("utf-8-sig").splitlines()
                  if line.strip() and not line.lstrip().startswith("#")]
        receipt=json.loads((Path(folder)/"quality.json").read_text())
        if (receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED"
            or receipt.get("trade_gate")!="BLOCKED" or receipt.get("paid_api_calls")!=0
            or receipt.get("manifest_sha256")!=expected["sha256"]
            or receipt.get("query_attempts")!=expected["count"]
            or receipt.get("issuer_count")!=expected["count"]
            or len(receipt.get("results",[]))!=expected["count"]
            or len(intended)!=expected["count"]):
            raise ValueError("source receipt does not match shard")
        actual=[r.get("code") for r in receipt["results"]]
        if len(set(intended))!=len(intended) or actual!=intended:
            raise ValueError("original issuer ordering or membership mismatch")
        for row in receipt["results"]:
            code=row["code"]
            if code in codes:raise ValueError("duplicate issuer across shards")
            codes.add(code)
            if row.get("status")!="OBSERVED_UNVERIFIED":
                raise ValueError("original unverified")
            file_raw=(Path(folder)/(code.replace(".","_")+".csv")).read_bytes()
            if hashlib.sha256(file_raw).hexdigest()!=row.get("sha256"):
                raise ValueError("CSV SHA mismatch")
            a,s=_csv_replay(file_raw,code,row)
            active_rows+=a;suspended_rows+=s;total+=1
    return {"phase":"P1_FOUR_SHARD_INDEPENDENT_BAR_REPLAY",
            "verified_shards":len(items),"verified_issuers":total,
            "independently_checked_active_rows":active_rows,
            "independently_checked_suspended_rows":suspended_rows,
            "provider_start":START,"provider_end":END,
            "source_sha256":plan["source_sha256"],
            "official_exchange_authenticated":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True);p.add_argument("--manifest-root",required=True)
    p.add_argument("--receipt",action="append",required=True)
    a=p.parse_args()
    items=[]
    for spec in a.receipt:
        index,folder=spec.split(":",1)
        items.append((int(index),Path(folder)))
    result=verify(json.loads(Path(a.plan).read_text()),items,a.manifest_root)
    print(json.dumps(result))
if __name__=="__main__":main()
