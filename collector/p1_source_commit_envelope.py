"""Read-only immutable Git-commit envelope for a SHA-replayed P1 handoff.

Bind the exact source archive commit, execution-code commit, eligible source
file inventory and separate archive_status.json digests. This is source-only
provenance; a target repo must independently fetch and rehash the bytes.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA=re.compile(r"[a-f0-9]{40}\\Z")
SHA256=re.compile(r"[a-f0-9]{64}\\Z")
STATUS=re.compile(r"[a-f0-9]{16}/archive_status[.]json\\Z")


def seal(handoff,replay,source_commit,execution_commit):
    if (not isinstance(source_commit,str) or not SHA.fullmatch(source_commit)
        or not isinstance(execution_commit,str) or not SHA.fullmatch(execution_commit)
        or source_commit=="0"*40 or execution_commit=="0"*40):
        raise ValueError("source and code commits must be real-looking 40-character Git SHAs")
    if (not isinstance(handoff,dict) or
        handoff.get("phase")!="P1_SOURCE_SHA_HANDOFF_NO_DESTINATION_ATTESTATION"
        or handoff.get("status")!="SOURCE_MANIFEST_REPLAYED_TARGET_UNVERIFIED"
        or handoff.get("trade_gate")!="BLOCKED"
        or handoff.get("orders")!=[]
        or handoff.get("executable_candidates")!=[]
        or any(handoff.get(k) is not False for k in (
            "migration_performed","destination_files_verified",
            "automatic_copy_authorized","writer_cutover_authorized",
            "historical_PIT_verified"))):
        raise ValueError("unsafe source handoff")
    if (not isinstance(replay,dict) or
        replay.get("phase")!="P1_SOURCE_HANDOFF_INDEPENDENT_BYTE_REPLAY"
        or replay.get("status")!="SOURCE_ONLY_SHA_REPLAYED_DESTINATION_UNVERIFIED"
        or replay.get("trade_gate")!="BLOCKED"
        or replay.get("orders")!=[]
        or replay.get("executable_candidates")!=[]
        or any(replay.get(k) is not False for k in (
            "destination_files_verified","migration_performed",
            "writer_cutover_authorized","historical_PIT_verified"))
        or replay.get("original_status_metadata_sha_separate") is not True):
        raise ValueError("unsafe independent source byte replay")
    epoch=handoff.get("source_epoch_sha256")
    digest=handoff.get("source_file_inventory_sha256")
    if (not isinstance(epoch,str) or not SHA256.fullmatch(epoch)
        or not isinstance(digest,str) or not SHA256.fullmatch(digest)
        or replay.get("source_epoch_sha256")!=epoch
        or replay.get("source_file_inventory_sha256")!=digest
        or type(handoff.get("eligible_shards")) is not int
        or type(handoff.get("eligible_original_files")) is not int
        or handoff["eligible_shards"]!=replay.get("source_shards_replayed")
        or handoff["eligible_original_files"]!=replay.get("source_files_replayed")
        or handoff.get("quarantined_source_shards") !=
           len(replay.get("quarantined_original_shards",[]))):
        raise ValueError("source handoff and independent replay mismatch")
    statuses=replay.get("archive_status_original_sha256")
    if (not isinstance(statuses,list) or not 1<=len(statuses)<=24):
        raise ValueError("unbounded archive status digest set")
    paths=set();reconstructed=[]
    for row in statuses:
        path=row.get("path") if isinstance(row,dict) else None
        h=row.get("sha256") if isinstance(row,dict) else None
        if (not isinstance(path,str) or not STATUS.fullmatch(path)
            or path in paths or not isinstance(h,str) or not SHA256.fullmatch(h)):
            raise ValueError("invalid archived original status digest")
        paths.add(path)
        reconstructed.append({"path":path,"sha256":h})
    reconstructed.sort(key=lambda x:x["path"])
    if f"{epoch[:16]}/archive_status.json" not in paths:
        raise ValueError("active source epoch status digest absent")
    source_only_evidence={
        "source_repo":"tiandi0228/ashare-free-data",
        "source_archive_ref":"research-csv-archive",
        "source_archive_commit_sha":source_commit,
        "execution_repo":"tiandi0228/ashare-free-data",
        "execution_main_commit_sha":execution_commit,
        "source_epoch_sha256":epoch,
        "eligible_file_inventory_sha256":digest,
        "eligible_original_files":handoff["eligible_original_files"],
        "eligible_source_shards":handoff["eligible_shards"],
        "archive_status_original_sha256":reconstructed,
        "quarantined_original_shards":sorted(replay["quarantined_original_shards"]),
    }
    canonical=json.dumps(source_only_evidence,sort_keys=True,
                         separators=(",",":"),ensure_ascii=False).encode()
    return {
        "phase":"P1_IMMUTABLE_SOURCE_HANDOFF_COMMIT_ENVELOPE",
        "status":"SOURCE_GIT_SNAPSHOT_SHA_BOUND_TARGET_UNVERIFIED",
        **source_only_evidence,
        "source_handoff_envelope_sha256":hashlib.sha256(canonical).hexdigest(),
        "envelope_digest_format":"JSON_SORT_KEYS_COMPACT_UTF8",
        "git_commit_ids_from_checked_out_source_and_code":True,
        "destination_repo":"tiandi0228/scripts",
        "destination_commit_sha":None,
        "destination_files_verified":False,
        "source_originals_deleted":False,
        "migration_performed":False,
        "writer_cutover_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--handoff",type=Path,required=True)
    p.add_argument("--replay",type=Path,required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--execution-commit",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    obj=seal(json.loads(a.handoff.read_text()),
             json.loads(a.replay.read_text()),
             a.source_commit,a.execution_commit)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\\n")
    print(json.dumps({k:obj[k] for k in (
        "phase","status","source_archive_commit_sha",
        "execution_main_commit_sha","source_handoff_envelope_sha256",
        "eligible_original_files","destination_files_verified","trade_gate")}))


if __name__=="__main__":
    main()
