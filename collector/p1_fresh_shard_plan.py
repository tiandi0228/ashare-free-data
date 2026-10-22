"""Build deterministic bounded research shards from a fresh vendor roster; not historical PIT."""
import argparse,csv,hashlib,json
from pathlib import Path

CAP=8
def plan(source, out, requested_day):
    source=Path(source); out=Path(out)
    raw=source.read_bytes()
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    codes=[r["code"] for r in rows]
    if not 1000<=len(codes)<=6000 or len(set(codes))!=len(codes):
        raise ValueError("invalid current vendor mainboard roster size or duplicates")
    from collector.p1_roster_shard_manifest import CODE
    if any(not CODE.fullmatch(c) for c in codes):
        raise ValueError("non-mainboard code in vendor roster")
    codes=sorted(codes)
    groups=[codes[i:i+CAP] for i in range(0,len(codes),CAP)]
    out.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for i,group in enumerate(groups):
        name=f"shard_{i:04d}.txt"
        data=("\n".join(group)+"\n").encode()
        (out/name).write_bytes(data)
        receipts.append({"index":i,"name":name,"count":len(group),"sha256":hashlib.sha256(data).hexdigest()})
    result={"phase":"P1_FRESH_VENDOR_SHARD_PLAN","requested_day":requested_day,
            "source_sha256":hashlib.sha256(raw).hexdigest(),"issuer_count":len(codes),
            "shard_size_cap":CAP,"shard_count":len(groups),"shards":receipts,
            "historical_PIT_verified":False,"complete_historical_ST_halt_delist_verified":False,
            "full_market_bars_observed":False,"paid_api_calls":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    (out/"plan.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    p.add_argument("--requested-day",required=True)
    a=p.parse_args()
    print(json.dumps(plan(a.source,a.out,a.requested_day),ensure_ascii=False))
if __name__=="__main__":main()
