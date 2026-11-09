"""Read-only SHA-gated migration inventory, never a migration permission.

Every eligible shard must have an original quality receipt and every source
CSV SHA must match that receipt. Missing or mismatched receipts quarantine the
whole shard. This cannot independently prove historical PIT, and never copies.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA=re.compile(r"[a-f0-9]{64}\Z")
EPOCH=re.compile(r"[a-f0-9]{16}\Z")
SHARD=re.compile(r"shard_([0-9]{4})\Z")
CODE=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
MAX_EPOCHS=24
MAX_SHARDS=400
MAX_CODES=8


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("nonregular or symlinked source original")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(root,active_sha):
    root=Path(root)
    if not root.is_dir() or not isinstance(active_sha,str) or not SHA.fullmatch(active_sha):
        raise ValueError("invalid source archive or active SHA")
    epochs=sorted(p for p in root.iterdir() if p.is_dir() and EPOCH.fullmatch(p.name))
    if not 1<=len(epochs)<=MAX_EPOCHS or any(p.is_symlink() for p in epochs):
        raise ValueError("invalid source epoch directories")
    records=[];quarantine=[];source_epochs=[];active_seen=0
    for epoch in epochs:
        status=epoch/"archive_status.json"
        state=json.loads(status.read_text()) if status.is_file() and not status.is_symlink() else None
        if not isinstance(state,dict):
            raise ValueError("missing archive epoch status")
        sha=state.get("source_sha256")
        indices=state.get("archived_shards")
        if (not isinstance(sha,str) or not SHA.fullmatch(sha)
            or sha[:16]!=epoch.name or state.get("trade_gate")!="BLOCKED"
            or not isinstance(indices,list) or len(indices)>MAX_SHARDS
            or len(set(map(str,indices)))!=len(indices)
            or any(type(n) is not int or not 0<=n<MAX_SHARDS for n in indices)):
            raise ValueError("invalid archive status/epoch")
        active_seen+=int(sha==active_sha)
        found=set()
        for folder in sorted(epoch.glob("shard_*")):
            m=SHARD.fullmatch(folder.name)
            if not m or folder.is_symlink() or not folder.is_dir():
                raise ValueError("invalid archived shard folder")
            n=int(m.group(1))
            if n not in indices or n in found:
                raise ValueError("unadvertised or duplicated archived shard")
            found.add(n)
        for n in sorted(indices):
            folder=epoch/f"shard_{n:04d}"
            name=f"{epoch.name}/shard_{n:04d}"
            reason=None;files=[]
            if not folder.is_dir() or folder.is_symlink():
                reason="SHARD_DIRECTORY_MISSING"
            else:
                receipt=folder/"quality.json"
                if not receipt.is_file() or receipt.is_symlink():
                    reason="QUALITY_RECEIPT_MISSING"
                else:
                    try:
                        evidence=json.loads(receipt.read_text())
                        rows=evidence.get("results")
                        if (evidence.get("status")!="OBSERVED_SUBSET_UNVERIFIED"
                            or evidence.get("trade_gate")!="BLOCKED"
                            or evidence.get("historical_point_in_time_universe_verified") is not False
                            or evidence.get("orders")!=[]
                            or not isinstance(rows,list)
                            or not 1<=len(rows)<=MAX_CODES
                            or evidence.get("issuer_count")!=len(rows)):
                            raise ValueError("unsafe or incomplete quality receipt")
                        csvs=sorted(folder.glob("*.csv"))
                        if len(csvs)!=len(rows) or len(csvs)>MAX_CODES:
                            raise ValueError("unexpected source CSV count")
                        checked=set()
                        for row in rows:
                            code=row.get("code") if isinstance(row,dict) else None
                            expected=row.get("sha256") if isinstance(row,dict) else None
                            if (not isinstance(code,str) or not CODE.fullmatch(code)
                                or code in checked or row.get("status")!="OBSERVED_UNVERIFIED"
                                or not isinstance(expected,str) or not SHA.fullmatch(expected)):
                                raise ValueError("invalid source CSV receipt")
                            checked.add(code)
                            path=folder/(code.replace(".","_")+".csv")
                            if digest(path)!=expected:
                                raise ValueError("source CSV SHA mismatch")
                            files.append({"path":f"{name}/{path.name}","sha256":expected})
                        if {f.name for f in csvs}!={p["path"].rsplit("/",1)[1] for p in files}:
                            raise ValueError("CSV receipt names do not reconcile")
                        files.append({"path":f"{name}/quality.json","sha256":digest(receipt)})
                    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError):
                        reason="QUALITY_OR_CSV_SHA_NOT_RECONCILED"
            if reason:
                quarantine.append({"source_epoch_prefix":epoch.name,
                                   "shard_id":f"shard_{n:04d}",
                                   "reason":reason,
                                   "included_in_copy_plan":False})
            else:
                records.append({"source_epoch_prefix":epoch.name,
                                "shard_id":f"shard_{n:04d}",
                                "source_file_sha256":files,
                                "original_receipt_present":True,
                                "historical_PIT_verified":False})
        source_epochs.append({"prefix":epoch.name,"declared_shards":len(indices),
                              "observed_folders":len(found)})
    if active_seen!=1:
        raise ValueError("active source epoch not unique or absent")
    eligible_files=sum(len(x["source_file_sha256"]) for x in records)
    return {
        "phase":"P1_PARTIAL_SHA_PINNED_COPY_PLAN_RESEARCH_ONLY",
        "status":"PARTIAL_ISOLATION_REQUIRED_NO_CUTOVER" if quarantine else
                 "SOURCE_FILES_SHA_REPLAYED_TARGET_UNVERIFIED",
        "active_source_sha256":active_sha,
        "epoch_count":len(source_epochs),
        "epochs":source_epochs,
        "eligible_shards":len(records),
        "eligible_original_files":eligible_files,
        "quarantined_shards":len(quarantine),
        "quarantine":quarantine,
        "eligible_source_shards":records,
        "source_receipt_sha_verified_for_eligible":True,
        "destination_files_verified":False,
        "entire_legacy_archive_eligible":not bool(quarantine),
        "automatic_copy_authorized":False,
        "writer_cutover_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--active-epoch",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=plan(a.archive,a.active_epoch)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
        "phase","status","eligible_shards","eligible_original_files",
        "quarantined_shards","quarantine","trade_gate")},ensure_ascii=False))


if __name__=="__main__":
    main()
