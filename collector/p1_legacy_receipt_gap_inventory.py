"""Read-only inventory for archived P1 shards with missing original receipts.

It must never invent/reconstitute a 'quality.json' or certify the original
run. This is gap evidence for later recovery from independently stored originals.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

EPOCH=re.compile(r"[0-9a-f]{16}\Z")
CODE=re.compile(r"(?:sh|sz)_[0-9]{6}\.csv\Z")


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def inventory_missing_receipts(root):
    root=Path(root)
    if not root.is_dir():
        raise ValueError("archive root missing")
    gaps=[]
    scanned_statuses=0
    for status_path in sorted(root.glob("*/archive_status.json")):
        epoch=status_path.parent
        if not EPOCH.fullmatch(epoch.name):
            continue
        scanned_statuses+=1
        status=json.loads(status_path.read_text())
        sha=status.get("source_sha256")
        ids=status.get("archived_shards")
        if (not isinstance(sha,str) or len(sha)!=64 or not sha.startswith(epoch.name) or
                status.get("trade_gate")!="BLOCKED" or not isinstance(ids,list) or
                any(type(i) is not int or not 0<=i<=9999 for i in ids) or
                len(ids)!=len(set(ids))):
            raise ValueError("invalid source archive marker")
        for i in sorted(ids):
            shard=epoch/f"shard_{i:04d}"
            if (shard/"quality.json").is_file():
                continue
            files=[]
            if shard.is_dir():
                for p in sorted(shard.iterdir()):
                    if p.is_symlink() or not p.is_file() or not CODE.fullmatch(p.name):
                        raise ValueError("unexpected original without quality receipt")
                    files.append({
                        "filename":p.name,
                        "sha256":digest(p),
                        "bytes":p.stat().st_size,
                    })
            gaps.append({
                "epoch_sha256":sha,
                "shard_index":i,
                "original_quality_json_present":False,
                "original_csv_file_count":len(files),
                "original_csv_files":files,
                "original_receipt_recovered":False,
                "historical_PIT_verified":False,
            })
    return {
        "phase":"P1_LEGACY_ARCHIVE_ORIGINAL_RECEIPT_GAPS",
        "status":("ORIGINAL_RECEIPTS_NOT_RECOVERED" if gaps else
                  "NO_SOURCE_STATUS_FOUND" if not scanned_statuses else
                  "NO_MISSING_RECEIPTS_IN_SCANNED_STATUSES"),
        "scanned_source_statuses":scanned_statuses,
        "missing_original_receipts":len(gaps),
        "retained_original_csv_files":sum(len(g["original_csv_files"]) for g in gaps),
        "gaps":gaps,
        "original_receipt_authenticity_certified":False,
        "all_epoch_archive_complete":False,  # A gap inventory cannot certify full archive completeness.
        "writer_cutover_authorized":False,
        "source_archive_deleted":False,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    result=inventory_missing_receipts(args.archive)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        k:v for k,v in result.items() if k!="gaps"
    }))
if __name__=="__main__":
    main()
