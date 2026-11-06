"""Read-only source archive/checkpoint reconciliation for safe cross-repo migration.

An independently persisted checkpoint does not prove original CSV bytes exist.
Outputs evidence gaps but never certifies historical PIT or enables trading.
"""
import argparse
import hashlib
import json
from pathlib import Path
from collector.p1_checkpoint import validate as validate_checkpoint

def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def examine(checkpoint, archive_root):
    validate_checkpoint(checkpoint)
    root=Path(archive_root)/checkpoint["source_sha256"][:16]
    state=root/"archive_status.json"
    report={
        "phase":"P1_MIGRATION_SOURCE_ARCHIVE_READINESS",
        "source_epoch_sha256":checkpoint["source_sha256"],
        "checkpoint_completed_shards":checkpoint["completed_shards"],
        "checkpoint_completed_issuers":checkpoint["completed_issuers"],
        "archive_status_found":state.is_file(),
        "archive_status_matches_epoch":False,
        "verified_original_shards":0,
        "verified_original_csv_files":0,
        "missing_or_invalid_shard_count":0,
        "missing_or_invalid_shards_sample":[],
        "all_checkpoint_originals_durably_located":False,
        "destination_mirror_verified":False,
        "writer_cutover_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]
    }
    if not state.is_file():
        report["status"]="ACTIVE_EPOCH_ARCHIVE_NOT_FOUND"
        report["missing_or_invalid_shard_count"]=checkpoint["completed_shards"]
        report["missing_or_invalid_shards_sample"]=[x["index"] for x in checkpoint["completed"][:20]]
        return report
    status=json.loads(state.read_text())
    archived=status.get("archived_shards")
    if (status.get("source_sha256")!=checkpoint["source_sha256"] or
        status.get("trade_gate")!="BLOCKED" or not isinstance(archived,list) or
        any(type(i) is not int for i in archived) or len(archived)!=len(set(archived))):
        report["status"]="ARCHIVE_STATUS_INVALID_OR_WRONG_EPOCH"
        report["missing_or_invalid_shard_count"]=checkpoint["completed_shards"]
        return report
    report["archive_status_matches_epoch"]=True
    declared=set(archived)
    missing=[]
    for item in checkpoint["completed"]:
        i=item["index"]
        folder=root/f"shard_{i:04d}"
        receipt_path=folder/"quality.json"
        if i not in declared or not receipt_path.is_file():
            missing.append(i);continue
        try:
            receipt=json.loads(receipt_path.read_text())
            digest=hashlib.sha256(json.dumps(receipt,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if (digest!=item["receipt_sha256"] or
                receipt.get("manifest_sha256")!=item["manifest_sha256"] or
                receipt.get("issuer_count")!=item["issuer_count"] or
                receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or
                receipt.get("trade_gate")!="BLOCKED" or
                receipt.get("historical_point_in_time_universe_verified") is not False or
                receipt.get("orders")!=[]):
                missing.append(i);continue
            rows=receipt.get("results")
            if not isinstance(rows,list) or len(rows)!=item["issuer_count"]:
                missing.append(i);continue
            verified=set()
            for row in rows:
                code=row["code"]
                if (not isinstance(code,str) or code in verified or
                    row.get("status")!="OBSERVED_UNVERIFIED" or
                    not isinstance(row.get("sha256"),str) or len(row["sha256"])!=64):
                    raise ValueError("invalid source issuer")
                verified.add(code)
                csv=folder/(code.replace(".","_")+".csv")
                if not csv.is_file() or _digest(csv)!=row["sha256"]:
                    raise ValueError("missing or invalid source CSV")
            report["verified_original_shards"]+=1
            report["verified_original_csv_files"]+=len(verified)
        except (KeyError,ValueError,TypeError,OSError,json.JSONDecodeError):
            missing.append(i)
    report["missing_or_invalid_shard_count"]=len(missing)
    report["missing_or_invalid_shards_sample"]=missing[:20]
    report["all_checkpoint_originals_durably_located"]=(
        not missing and report["verified_original_csv_files"]==checkpoint["completed_issuers"])
    report["status"]=(
        "CHECKPOINT_SOURCE_ORIGINALS_PRESENT_SHA_VERIFIED" if
        report["all_checkpoint_originals_durably_located"] else
        "CHECKPOINT_ORIGINALS_INCOMPLETE_NO_CUTOVER")
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--checkpoint",required=True,type=Path)
    ap.add_argument("--archive",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    report=examine(json.loads(args.checkpoint.read_text()),args.archive)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":main()
