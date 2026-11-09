"""Fail-closed read-only source handoff receipt for later independent target SHA readback.

No bytes are copied, no original is reconstructed and no destination is
certified. This binds an exact canonical file inventory to the active P1
checkpoint audit and a separate all-epoch gap inventory.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA=re.compile(r"[a-f0-9]{64}\Z")
PATH=re.compile(r"[a-f0-9]{16}/shard_[0-9]{4}/(?:quality[.]json|(?:sh|sz)_[0-9]{6}[.]csv)\Z")
MAX_SHARDS=400
MAX_FILES=MAX_SHARDS*9


def build(partial,ready,gaps):
    if (not isinstance(partial,dict) or
        partial.get("phase")!="P1_PARTIAL_SHA_PINNED_COPY_PLAN_RESEARCH_ONLY" or
        partial.get("trade_gate")!="BLOCKED" or partial.get("orders")!=[] or
        partial.get("automatic_copy_authorized") is not False or
        partial.get("writer_cutover_authorized") is not False or
        partial.get("destination_files_verified") is not False or
        partial.get("historical_PIT_verified") is not False):
        raise ValueError("unsafe P1 source inventory")
    epoch=partial.get("active_source_sha256")
    if not isinstance(epoch,str) or not SHA.fullmatch(epoch):
        raise ValueError("missing active source SHA")
    if (not isinstance(ready,dict) or
        ready.get("phase")!="P1_MIGRATION_SOURCE_ARCHIVE_READINESS" or
        ready.get("source_epoch_sha256")!=epoch or
        ready.get("status")!="CHECKPOINT_SOURCE_ORIGINALS_PRESENT_SHA_VERIFIED" or
        ready.get("all_checkpoint_originals_durably_located") is not True or
        ready.get("archive_status_matches_epoch") is not True or
        ready.get("missing_or_invalid_shard_count")!=0 or
        ready.get("verified_original_shards")!=ready.get("checkpoint_completed_shards") or
        ready.get("verified_original_csv_files")!=ready.get("checkpoint_completed_issuers") or
        ready.get("writer_cutover_authorized") is not False or
        ready.get("destination_mirror_verified") is not False or
        ready.get("historical_PIT_verified") is not False or
        ready.get("trade_gate")!="BLOCKED" or ready.get("orders")!=[]):
        raise ValueError("active checkpoint source SHA not independently reconciled")
    if (not isinstance(gaps,dict) or
        gaps.get("phase")!="P1_LEGACY_ORIGINAL_RECEIPT_GAP_AUDIT" or
        gaps.get("active_source_sha256")!=epoch or
        gaps.get("trade_gate")!="BLOCKED" or gaps.get("orders")!=[] or
        gaps.get("writer_cutover_authorized") is not False or
        gaps.get("destination_mirror_verified") is not False or
        gaps.get("missing_receipts_synthesized") is not False):
        raise ValueError("untrusted missing receipt inventory")
    records=partial.get("eligible_source_shards")
    quarantine=partial.get("quarantine")
    if (not isinstance(records,list) or len(records)>MAX_SHARDS*24 or
        not isinstance(quarantine,list) or len(quarantine)>MAX_SHARDS*24 or
        len(records)!=partial.get("eligible_shards") or
        len(quarantine)!=partial.get("quarantined_shards") or
        type(gaps.get("missing_receipts_total")) is not int or
        gaps["missing_receipts_total"]!=len(gaps.get("missing_original_receipts",[]))):
        raise ValueError("partial source inventory is not reconciled")
    known_shards=set();seen_paths=set();entries=[];active_shards=0;active_issuers=0
    for row in records:
        if (not isinstance(row,dict) or
            row.get("historical_PIT_verified") is not False or
            row.get("original_receipt_present") is not True):
            raise ValueError("untrusted eligible shard")
        prefix=row.get("source_epoch_prefix");shard=row.get("shard_id")
        if (not isinstance(prefix,str) or not re.fullmatch(r"[a-f0-9]{16}",prefix)
            or not isinstance(shard,str) or not re.fullmatch(r"shard_[0-9]{4}",shard)
            or (prefix,shard) in known_shards):
            raise ValueError("duplicate or malformed source shard")
        known_shards.add((prefix,shard))
        files=row.get("source_file_sha256")
        if not isinstance(files,list) or not 2<=len(files)<=9:
            raise ValueError("unbounded source file inventory")
        if sum(x.get("path","").endswith("/quality.json") for x in files if isinstance(x,dict))!=1:
            raise ValueError("missing eligible quality receipt entry")
        for item in files:
            path=item.get("path") if isinstance(item,dict) else None
            digest=item.get("sha256") if isinstance(item,dict) else None
            if (not isinstance(path,str) or not PATH.fullmatch(path)
                or not path.startswith(f"{prefix}/{shard}/")
                or path in seen_paths or not isinstance(digest,str)
                or not SHA.fullmatch(digest)):
                raise ValueError("unsafe, duplicate or malformed original SHA path")
            seen_paths.add(path);entries.append({"path":path,"sha256":digest})
        if prefix==epoch[:16]:
            active_shards+=1
            active_issuers+=len(files)-1
    if len(entries)>MAX_FILES*24 or len(entries)!=partial.get("eligible_original_files"):
        raise ValueError("eligible source file count mismatch")
    missing=set()
    for row in quarantine:
        prefix=row.get("source_epoch_prefix") if isinstance(row,dict) else None
        shard=row.get("shard_id") if isinstance(row,dict) else None
        if (not isinstance(prefix,str) or not re.fullmatch(r"[a-f0-9]{16}",prefix)
            or not isinstance(shard,str) or not re.fullmatch(r"shard_[0-9]{4}",shard)
            or (prefix,shard) in known_shards or (prefix,shard) in missing or
            row.get("included_in_copy_plan") is not False):
            raise ValueError("unsafe quarantine row")
        missing.add((prefix,shard))
    official_gaps=set()
    for row in gaps["missing_original_receipts"]:
        prefix=row.get("source_epoch_prefix") if isinstance(row,dict) else None
        shard=row.get("shard_id") if isinstance(row,dict) else None
        if not isinstance(prefix,str) or not isinstance(shard,str):
            raise ValueError("invalid legacy gap")
        official_gaps.add((prefix,shard))
    if (not official_gaps.issubset(missing) or
        active_shards!=ready["checkpoint_completed_shards"] or
        active_issuers!=ready["checkpoint_completed_issuers"] or
        any(prefix==epoch[:16] for prefix,_ in missing)):
        raise ValueError("current checkpoint or historical gap no longer matches eligible file plan")
    # Deterministic handoff inventory digest can be recomputed from source bytes
    # and compared against a separate destination checkout after a future copy.
    entries.sort(key=lambda x:x["path"])
    raw=json.dumps(entries,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return {
        "phase":"P1_SOURCE_SHA_HANDOFF_NO_DESTINATION_ATTESTATION",
        "status":"SOURCE_MANIFEST_REPLAYED_TARGET_UNVERIFIED",
        "source_epoch_sha256":epoch,
        "active_verified_shards":active_shards,
        "active_verified_csv_issuers":active_issuers,
        "eligible_shards":len(records),
        "eligible_original_files":len(entries),
        "quarantined_source_shards":len(missing),
        "missing_original_quality_receipts":len(official_gaps),
        "source_file_inventory_sha256":hashlib.sha256(raw).hexdigest(),
        "canonical_inventory_format":"JSON_SORT_KEYS_COMPACT_UTF8_SORTED_BY_PATH",
        "original_paths_and_sha256":entries,
        "source_manifest_has_no_archive_status_files":True,
        "active_epoch_checkpoint_sha_anchored_separately":True,
        "destination_files_verified":False,
        "migration_performed":False,
        "automatic_copy_authorized":False,
        "writer_cutover_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--partial-plan",type=Path,required=True)
    p.add_argument("--readiness",type=Path,required=True)
    p.add_argument("--legacy-gaps",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    receipt=build(json.loads(args.partial_plan.read_text()),
                  json.loads(args.readiness.read_text()),
                  json.loads(args.legacy_gaps.read_text()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:receipt[k] for k in (
        "phase","status","active_verified_shards","active_verified_csv_issuers",
        "eligible_shards","eligible_original_files","quarantined_source_shards",
        "source_file_inventory_sha256","destination_files_verified","trade_gate")},ensure_ascii=False))


if __name__=="__main__":
    main()
