"""Offline checkpoint for bounded research refresh batches; no provider calls."""
import argparse, hashlib, json, re
from pathlib import Path

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def reconcile(manifest, receipts):
    if manifest["trade_gate"]!="BLOCKED" or manifest["orders"]!=[] or manifest["executable_candidates"]!=[] or manifest["historical_PIT_verified"] is not False:
        raise ValueError("unsafe manifest")
    batches=manifest["batches"]
    if manifest["batch_size"]!=8 or len(batches)!=manifest["batch_count"]:
        raise ValueError("invalid batch shape")
    seen=set()
    for i,b in enumerate(batches):
        if b["index"]!=i or not 1<=len(b["issuers"])<=8 or digest(b["issuers"])!=b["manifest_sha256"]:
            raise ValueError("invalid batch digest")
        for row in b["issuers"]:
            code=row["code"]
            if code in seen or not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",code) or not re.fullmatch("[0-9a-f]{64}",row["original_csv_sha256"]):
                raise ValueError("invalid issuer identity")
            seen.add(code)
    if len(seen)!=manifest["issuer_count"]:raise ValueError("issuer count mismatch")
    completed={}
    for r in receipts:
        i=r["batch_index"]
        if type(i) is not int or not 0<=i<len(batches) or i in completed:
            raise ValueError("invalid or duplicate receipt index")
        if r["epoch"]!=manifest["epoch"] or r["manifest_sha256"]!=batches[i]["manifest_sha256"] or r["asof"]!="2026-11-25":
            raise ValueError("receipt binding mismatch")
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["historical_PIT_verified"] is not False:
            raise ValueError("unsafe receipt")
        expected={x["code"]:x["original_csv_sha256"] for x in batches[i]["issuers"]}
        actual={}
        for row in r["results"]:
            code=row["code"]
            if code in actual or code not in expected or row["original_csv_sha256"]!=expected[code]:
                raise ValueError("issuer binding mismatch")
            if row["status"] not in ("FEATURE_WINDOW_OBSERVED","VENDOR_WINDOW_GAP") or not re.fullmatch("[0-9a-f]{64}",row["extension_sha256"]):
                raise ValueError("incomplete observation")
            actual[code]=row["original_csv_sha256"]
        if actual!=expected:raise ValueError("incomplete batch")
        completed[i]=r
    pending=[i for i in range(len(batches)) if i not in completed]
    # Receipt reconciliation is structural only: original extension bytes must
    # be independently replayed before any batch is admitted to coverage.
    return dict(epoch=manifest["epoch"],manifest_sha256=digest(manifest),target_asof="2026-11-25",
                total_batches=len(batches),structurally_complete_batches=len(completed),
                structurally_complete_issuers=sum(len(batches[i]["issuers"]) for i in completed),
                pending_batch_indices=pending,next_pending_batch=pending[0] if pending else None,
                provider_calls=0,coverage_batches_accepted=0,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--manifest",type=Path,required=True);p.add_argument("--receipts",type=Path,nargs="*",default=[]);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=reconcile(json.loads(a.manifest.read_bytes()),[json.loads(x.read_bytes()) for x in a.receipts]);a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P2_REFRESH_CHECKPOINT:",json.dumps({k:v for k,v in r.items() if k!="pending_batch_indices"}))
