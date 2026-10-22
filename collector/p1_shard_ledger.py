"""Conservative per-roster shard ledger: only verified receipts count as done."""
import argparse, hashlib, json
from pathlib import Path

def reconcile(plan, receipts, prior=None):
    if plan.get("phase")!="P1_FRESH_VENDOR_SHARD_PLAN":
        raise ValueError("invalid plan")
    shards=plan["shards"]
    if len(shards)!=plan["shard_count"] or len({s["index"] for s in shards})!=len(shards):
        raise ValueError("invalid shard plan")
    source=plan["source_sha256"]
    completed={}
    if prior:
        if prior.get("source_sha256")!=source or prior.get("shard_count")!=len(shards):
            raise ValueError("ledger belongs to another roster")
        for item in prior.get("completed",[]):
            index=item.get("index")
            if type(index) is not int or index in completed:
                raise ValueError("duplicate or invalid prior ledger index")
            completed[index]=item
    failed=[]
    for index, receipt in receipts:
        if type(index)!=int or not 0<=index<len(shards):
            raise ValueError("receipt shard out of range")
        expected=shards[index]
        if receipt.get("manifest_sha256")!=expected["sha256"] or receipt.get("issuer_count")!=expected["count"]:
            raise ValueError("receipt manifest mismatch")
        ok=(receipt.get("status")=="OBSERVED_SUBSET_UNVERIFIED" and
            receipt.get("trade_gate")=="BLOCKED" and receipt.get("paid_api_calls")==0 and
            receipt.get("query_attempts")==expected["count"] and
            len(receipt.get("results",[]))==expected["count"] and
            all(r.get("status")=="OBSERVED_UNVERIFIED" and len(r.get("sha256",""))==64 for r in receipt["results"]))
        if ok:
            completed[index]={"index":index,"manifest_sha256":expected["sha256"],
                              "issuer_count":expected["count"],"receipt_sha256":hashlib.sha256(
                                  json.dumps(receipt,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
        else:
            completed.pop(index,None)
            failed.append(index)
    valid=[]
    for i, entry in completed.items():
        if type(i)!=int or not 0<=i<len(shards) or entry.get("manifest_sha256")!=shards[i]["sha256"] or entry.get("issuer_count")!=shards[i]["count"] or len(entry.get("receipt_sha256",""))!=64:
            raise ValueError("corrupt prior ledger")
        valid.append(entry)
    done={x["index"] for x in valid}
    pending=[i for i in range(len(shards)) if i not in done]
    return {"phase":"P1_ROSTER_SHARD_LEDGER","source_sha256":source,
            "shard_count":len(shards),"completed":sorted(valid,key=lambda x:x["index"]),
            "completed_shards":len(done),"completed_issuers":sum(x["issuer_count"] for x in valid),
            "pending_shards":pending,"failed_in_this_reconciliation":sorted(set(failed)),
            "next_shard":pending[0] if pending else None,"full_market_bars_certified":False,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True);ap.add_argument("--receipt",action="append",default=[])
    ap.add_argument("--prior");ap.add_argument("--out",required=True)
    a=ap.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prior=json.loads(Path(a.prior).read_text()) if a.prior else None
    receipts=[]
    for spec in a.receipt:
        index,path=spec.split(":",1)
        receipts.append((int(index),json.loads(Path(path).read_text())))
    result=reconcile(plan,receipts,prior)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("completed","pending_shards")}))
if __name__=="__main__":main()
