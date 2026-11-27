"""Independently replay a bounded refresh receipt using both CSV originals."""
import argparse,hashlib,json,re
from pathlib import Path
from collector.p2_refresh_checkpoint import reconcile,digest
from collector.p2_gap_extension_replay import inspect

def checked_bytes(p,sha):
    if p.is_symlink() or not p.is_file() or p.stat().st_size>250000:
        raise ValueError("invalid original file")
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError("original SHA mismatch")
    return raw

def verify(manifest,receipt,root,extension_dir):
    reconcile(manifest,[receipt])
    batch=manifest["batches"][receipt["batch_index"]]
    if root.name!=manifest["epoch"][:16]:raise ValueError("wrong source epoch")
    by_code={r["code"]:r for r in receipt["results"]}
    rows=[]
    for source in batch["issuers"]:
        code=source["code"];shard=source["source_shard"]
        if not re.fullmatch(r"shard_[0-9]{4}",shard):raise ValueError("invalid shard")
        filename=code.replace(".","_")+".csv"
        row=by_code[code]
        a=checked_bytes(root/shard/filename,source["original_csv_sha256"])
        b=checked_bytes(extension_dir/filename,row["extension_sha256"])
        detail=inspect(a,b,code)
        expected="FEATURE_WINDOW_OBSERVED" if detail["recovered_at_new_cutoff"] else "VENDOR_WINDOW_GAP"
        if row["status"]!=expected or row.get("research_features")!=detail["research_features"]:
            raise ValueError("claimed features differ from replay")
        rows.append(dict(code=code,original_csv_sha256=source["original_csv_sha256"],status=expected,**detail))
    return dict(epoch=manifest["epoch"],batch_index=batch["index"],manifest_sha256=batch["manifest_sha256"],
                receipt_sha256=digest(receipt),asof=receipt["asof"],issuer_count=len(rows),
                research_feature_issuers=sum(x["recovered_at_new_cutoff"] for x in rows),
                research_gap_issuers=sum(not x["recovered_at_new_cutoff"] for x in rows),
                original_bytes_replayed=True,official_sessions_verified=False,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[],results=rows)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("manifest","receipt","archive-epoch","extension-dir","out"):p.add_argument("--"+arg,type=Path,required=True)
    a=p.parse_args()
    r=verify(json.loads(a.manifest.read_bytes()),json.loads(a.receipt.read_bytes()),a.archive_epoch,a.extension_dir)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P2_BATCH_REPLAY:",json.dumps({k:v for k,v in r.items() if k!="results"}))
