"""Read-only per-epoch original archive receipt gap inventory (NO TRADES).

This inventory establishes that shard quality receipts exist, not that their
bytes, original CSV, or the historical universe are independently certified.
Never synthesize or rewrite a missing receipt. Current epoch SHA verification
must be performed separately by p1_archive_migration_readiness.
"""
import argparse
import json
import re
from pathlib import Path

PHASE="P1_LEGACY_ORIGINAL_RECEIPT_GAP_AUDIT"
EPOCH=re.compile(r"[a-f0-9]{16}\Z")
MAX_EPOCHS=24
MAX_SHARDS=400
MAX_CSV_PER_SHARD=8


def inspect(root,active_epoch):
    if not isinstance(active_epoch,str) or not re.fullmatch(r"[a-f0-9]{64}",active_epoch):
        raise ValueError("invalid active source SHA")
    root=Path(root)
    if not root.is_dir():
        raise ValueError("source archive root missing")
    epochs=sorted(p for p in root.iterdir() if p.is_dir() and EPOCH.fullmatch(p.name))
    if not epochs or len(epochs)>MAX_EPOCHS:
        raise ValueError("missing or unbounded original epochs")
    if any(p.is_symlink() for p in epochs):
        raise ValueError("symlinked epoch archive forbidden")
    result=[];overall_gaps=[]
    for epoch in epochs:
        status_file=epoch/"archive_status.json"
        if status_file.is_symlink() or not status_file.is_file():
            raise ValueError("missing original epoch archive status")
        state=json.loads(status_file.read_text())
        sha=state.get("source_sha256")
        advertised=state.get("archived_shards")
        if (not isinstance(sha,str) or not re.fullmatch(r"[a-f0-9]{64}",sha)
            or sha[:16]!=epoch.name
            or state.get("trade_gate")!="BLOCKED"
            or not isinstance(advertised,list)
            or len(advertised)>MAX_SHARDS
            or any(type(i) is not int or not 0<=i<MAX_SHARDS for i in advertised)
            or len(set(advertised))!=len(advertised)):
            raise ValueError("unsafe source archive status")
        declared=set(advertised);observed=set();receipts=set();csv_count=0
        for folder in sorted(epoch.glob("shard_*")):
            if folder.is_symlink() or not folder.is_dir():
                raise ValueError("untrusted shard directory")
            match=re.fullmatch(r"shard_([0-9]{4})",folder.name)
            if not match or int(match.group(1)) not in declared:
                raise ValueError("unadvertised original shard")
            number=int(match.group(1))
            if number in observed:
                raise ValueError("duplicate shard directory")
            observed.add(number)
            quality=folder/"quality.json"
            if quality.is_symlink():
                raise ValueError("symlinked quality receipt")
            if quality.is_file():
                receipts.add(number)
            files=list(folder.glob("*.csv"))
            if len(files)>MAX_CSV_PER_SHARD or any(
                f.is_symlink() or not f.is_file() for f in files):
                raise ValueError("unbounded or symlinked CSV originals")
            csv_count+=len(files)
        missing=sorted(declared-receipts)
        gaps=[{"source_epoch_prefix":epoch.name,"shard_id":f"shard_{i:04d}",
               "reason":"ORIGINAL_QUALITY_RECEIPT_MISSING_NOT_RECONSTRUCTIBLE"}
              for i in missing]
        overall_gaps.extend(gaps)
        result.append({
            "source_epoch_prefix":epoch.name,
            "is_active_source_epoch":sha==active_epoch,
            "archive_status_advertised_shards":len(declared),
            "observed_shard_directories":len(observed),
            "existing_quality_receipts":len(receipts),
            "observed_csv_files":csv_count,
            "missing_quality_receipts":len(missing),
            "missing_quality_shard_ids":[f"shard_{i:04d}" for i in missing],
            "all_source_bytes_sha_verified_by_this_report":False,
        })
    if sum(x["is_active_source_epoch"] for x in result)!=1:
        raise ValueError("active source epoch not present exactly once")
    return {
        "phase":PHASE,
        "status":("ALL_EPOCH_RECEIPTS_PRESENT_NOT_BYTE_VERIFIED"
                  if not overall_gaps else "LEGACY_QUALITY_RECEIPT_GAPS_NO_CUTOVER"),
        "active_source_sha256":active_epoch,
        "epochs_observed":len(result),
        "original_csv_files_observed":sum(x["observed_csv_files"] for x in result),
        "missing_receipts_total":len(overall_gaps),
        "missing_original_receipts":overall_gaps,
        "epochs":result,
        "original_csv_bytes_sha_verified_by_this_report":False,
        "missing_receipts_synthesized":False,
        "destination_mirror_verified":False,
        "writer_cutover_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--active-epoch",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=inspect(a.archive,a.active_epoch)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "phase":result["phase"],
        "status":result["status"],
        "epochs_observed":result["epochs_observed"],
        "missing_receipts_total":result["missing_receipts_total"],
        "missing_original_receipts":result["missing_original_receipts"],
        "trade_gate":result["trade_gate"]},ensure_ascii=False))


if __name__=="__main__":
    main()
