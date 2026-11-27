"""Read-only deterministic full-universe refresh manifest, not a collection trigger."""
import argparse,hashlib,json,re
from pathlib import Path

BATCH_SIZE=8
def build(coverage,root):
    epoch=coverage["source_epoch_sha256"]
    if root.name!=epoch[:16] or coverage.get("trade_gate")!="BLOCKED" or coverage.get("full_archive_evidence_accounted") is not True or coverage.get("historical_PIT_verified") is not False:
        raise ValueError("wrong or unsafe frozen coverage")
    items={}
    for p in sorted(root.glob("shard_*/quality.json")):
        receipt=json.loads(p.read_bytes())
        if receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or receipt.get("trade_gate")!="BLOCKED" or receipt.get("historical_point_in_time_universe_verified") is not False:
            raise ValueError("unsafe source receipt")
        for r in receipt["results"]:
            code=r["code"]
            if code in items or not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",code) or r["status"]!="OBSERVED_UNVERIFIED":
                raise ValueError("invalid or duplicate issuer")
            digest=hashlib.sha256((p.parent/(code.replace(".","_")+".csv")).read_bytes()).hexdigest()
            if digest!=r["sha256"]:raise ValueError("source hash mismatch")
            items[code]=dict(code=code,source_shard=p.parent.name,original_csv_sha256=digest)
    if len(items)!=coverage["observed_feature_or_gap_issuers"]:raise ValueError("universe count mismatch")
    gaps=set(coverage["gap_issuer_codes"])
    if not gaps<=items.keys():raise ValueError("missing gap issuer")
    # Prioritize the remaining 3170; previously checked gaps are separately scoped.
    ordered=sorted(items,key=lambda c:(c in gaps,c))
    batches=[]
    for i in range(0,len(ordered),BATCH_SIZE):
        rows=[items[c] for c in ordered[i:i+BATCH_SIZE]]
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        batches.append(dict(index=len(batches),manifest_sha256=digest,issuers=rows))
    return dict(epoch=epoch,issuer_count=len(items),batch_count=len(batches),batch_size=BATCH_SIZE,
                historical_gap_issuers=len(gaps),batches=batches,provider_calls=0,refresh_started=False,
                historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--coverage",type=Path,required=True);p.add_argument("--archive-epoch",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=build(json.loads(a.coverage.read_bytes()),a.archive_epoch);a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P2_FULL_REFRESH_MANIFEST:",json.dumps({k:v for k,v in r.items() if k!="batches"}))
