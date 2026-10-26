"""Independently replay up to four P1 shard receipts and raw historical CSV hashes."""
import argparse,hashlib,json
from pathlib import Path

def verify(plan,items,manifest_root):
    if not 1<=len(items)<=4 or len(set(i for i,_ in items))!=len(items):
        raise ValueError("invalid distinct shard count")
    codes=set();total=0
    for index,folder in items:
        if not 0<=index<plan["shard_count"]:raise ValueError("out-of-range index")
        expected=plan["shards"][index]
        manifest=Path(manifest_root)/expected["name"]
        raw=manifest.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected["sha256"]:raise ValueError("manifest digest")
        intended=[line.strip() for line in raw.decode().splitlines() if line.strip() and not line.lstrip().startswith("#")]
        receipt=json.loads((Path(folder)/"quality.json").read_text())
        if (receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED"
            or receipt.get("trade_gate")!="BLOCKED" or receipt.get("paid_api_calls")!=0
            or receipt.get("manifest_sha256")!=expected["sha256"]
            or receipt.get("query_attempts")!=expected["count"]
            or receipt.get("issuer_count")!=expected["count"]
            or len(receipt.get("results",[]))!=expected["count"]
            or len(intended)!=expected["count"]):
            raise ValueError("source receipt does not match shard")
        if set(x.get("code") for x in receipt["results"])!=set(intended):
            raise ValueError("issuer list mismatch")
        for row in receipt["results"]:
            code=row["code"]
            if code in codes:raise ValueError("duplicate issuer across shards")
            codes.add(code)
            if row.get("status")!="OBSERVED_UNVERIFIED":raise ValueError("original unverified")
            csv=(Path(folder)/(code.replace(".","_")+".csv")).read_bytes()
            if hashlib.sha256(csv).hexdigest()!=row.get("sha256"):
                raise ValueError("CSV SHA mismatch")
            if not csv.startswith(b"date,code,"):raise ValueError("CSV header invalid")
            total+=1
    return {"phase":"P1_FOUR_SHARD_ORIGINAL_CSV_VERIFY","verified_shards":len(items),
            "verified_issuers":total,"source_sha256":plan["source_sha256"],
            "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True);p.add_argument("--manifest-root",required=True)
    p.add_argument("--receipt",action="append",required=True)
    a=p.parse_args()
    items=[]
    for s in a.receipt:
        index,folder=s.split(":",1);items.append((int(index),Path(folder)))
    print(json.dumps(verify(json.loads(Path(a.plan).read_text()),items,a.manifest_root)))
if __name__=="__main__":main()
