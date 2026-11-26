"""Aggregate only independently replayed batch originals; never trust summary claims."""
import argparse,json,re
from pathlib import Path
from collector.p2_refresh_checkpoint import reconcile
from collector.p2_refresh_batch_replay import verify

def aggregate(manifest,root,packages):
    receipts=[]
    for p in packages:
        if not p.is_dir() or p.is_symlink():raise ValueError("invalid package")
        receipts.append(json.loads((p/"receipt.json").read_bytes()))
    structural=reconcile(manifest,receipts)
    rows=[]
    accepted=[]
    for p,r in zip(packages,receipts):
        verified=verify(manifest,r,root,p)
        if verified["original_bytes_replayed"] is not True or verified["trade_gate"]!="BLOCKED" or verified["orders"]!=[] or verified["executable_candidates"]!=[]:
            raise ValueError("unsafe independent replay")
        accepted.append(verified["batch_index"])
        rows.extend(verified["results"])
    if len(rows)!=structural["structurally_complete_issuers"] or len({r["code"] for r in rows})!=len(rows):
        raise ValueError("issuer aggregation mismatch")
    features=sum(r["recovered_at_new_cutoff"] is True for r in rows)
    return dict(epoch=manifest["epoch"],target_asof=structural["target_asof"],manifest_sha256=structural["manifest_sha256"],
                universe_issuers=manifest["issuer_count"],total_batches=manifest["batch_count"],
                accepted_batches=len(accepted),accepted_batch_indices=sorted(accepted),
                accepted_issuers=len(rows),research_feature_issuers=features,research_gap_issuers=len(rows)-features,
                unobserved_issuers=manifest["issuer_count"]-len(rows),pending_batch_indices=structural["pending_batch_indices"],
                next_pending_batch=structural["next_pending_batch"],
                full_universe_observed=len(rows)==manifest["issuer_count"],
                official_sessions_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],
                results=sorted(rows,key=lambda r:r["code"]))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--archive-epoch",type=Path,required=True)
    p.add_argument("--packages",type=Path,nargs="*",default=[]);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=aggregate(json.loads(a.manifest.read_bytes()),a.archive_epoch,a.packages)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P2_REFRESH_AGGREGATE:",json.dumps({k:v for k,v in r.items() if k not in ("results","pending_batch_indices","accepted_batch_indices")}))
