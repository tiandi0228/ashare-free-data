"""Second-pass read-only byte replay of the P1 source handoff.

Independently rehash source files listed in the handoff and enumerate ALL
archived shard folders against every archived status. Archived status SHA
proofs are separate from the original handoff's file list. This produces no
destination attestation, copy command, or writer authorization.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA=re.compile(r"[a-f0-9]{64}\Z")
EPOCH=re.compile(r"[a-f0-9]{16}\Z")
SHARD=re.compile(r"shard_([0-9]{4})\Z")
FILE=re.compile(r"[a-f0-9]{16}/shard_[0-9]{4}/(?:quality[.]json|(?:sh|sz)_[0-9]{6}[.]csv)\Z")
MAX_EPOCHS=24
MAX_SHARDS=400
MAX_FILE_ENTRIES=MAX_EPOCHS*MAX_SHARDS*9


def hash_original(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("source original absent or symlinked")
    sha=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            sha.update(block)
    return sha.hexdigest()


def replay(root,manifest):
    root=Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("source archive directory unavailable")
    if (not isinstance(manifest,dict)
        or manifest.get("phase")!="P1_SOURCE_SHA_HANDOFF_NO_DESTINATION_ATTESTATION"
        or manifest.get("status")!="SOURCE_MANIFEST_REPLAYED_TARGET_UNVERIFIED"
        or manifest.get("canonical_inventory_format")!="JSON_SORT_KEYS_COMPACT_UTF8_SORTED_BY_PATH"
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("orders")!=[]
        or manifest.get("executable_candidates")!=[]
        or any(manifest.get(k) is not False for k in (
            "destination_files_verified","migration_performed",
            "automatic_copy_authorized","writer_cutover_authorized",
            "historical_PIT_verified"))
        or manifest.get("source_manifest_has_no_archive_status_files") is not True):
        raise ValueError("unsafe or non-source P1 handoff manifest")
    active=manifest.get("source_epoch_sha256")
    rows=manifest.get("original_paths_and_sha256")
    given_hash=manifest.get("source_file_inventory_sha256")
    if (not isinstance(active,str) or not SHA.fullmatch(active)
        or not isinstance(given_hash,str) or not SHA.fullmatch(given_hash)
        or not isinstance(rows,list) or not 1<=len(rows)<=MAX_FILE_ENTRIES
        or type(manifest.get("eligible_original_files")) is not int
        or len(rows)!=manifest["eligible_original_files"]):
        raise ValueError("invalid source handoff file count")
    accepted={};previous=""
    for row in rows:
        p=row.get("path") if isinstance(row,dict) else None
        d=row.get("sha256") if isinstance(row,dict) else None
        if (not isinstance(p,str) or not FILE.fullmatch(p)
            or not isinstance(d,str) or not SHA.fullmatch(d)
            or p<=previous):
            raise ValueError("unsafe, unsorted, or duplicate handoff file")
        previous=p
        accepted[p]=d
    raw=json.dumps(rows,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    if hashlib.sha256(raw).hexdigest()!=given_hash:
        raise ValueError("canonical source handoff checksum mismatch")
    epochs=sorted(p for p in root.iterdir() if p.is_dir() and EPOCH.fullmatch(p.name))
    if not 1<=len(epochs)<=MAX_EPOCHS or any(p.is_symlink() for p in epochs):
        raise ValueError("bad source epoch directory set")
    active_seen=0;replayed=0;quarantined=[];status_shas=[];matched=set()
    for epoch in epochs:
        status=epoch/"archive_status.json"
        status_hash=hash_original(status)
        obj=json.loads(status.read_text(encoding="utf-8"))
        sha=obj.get("source_sha256")
        ids=obj.get("archived_shards")
        if (not isinstance(sha,str) or not SHA.fullmatch(sha)
            or sha[:16]!=epoch.name or obj.get("trade_gate")!="BLOCKED"
            or not isinstance(ids,list) or len(ids)>MAX_SHARDS
            or len(set(map(str,ids)))!=len(ids)
            or any(type(n) is not int or not 0<=n<MAX_SHARDS for n in ids)):
            raise ValueError("unsafe original status metadata")
        active_seen+=int(active==sha)
        status_shas.append({"path":f"{epoch.name}/archive_status.json",
                            "sha256":status_hash})
        observed=set()
        for folder in epoch.glob("shard_*"):
            m=SHARD.fullmatch(folder.name)
            if (not m or folder.is_symlink() or not folder.is_dir()
                or int(m.group(1)) not in ids):
                raise ValueError("unadvertised original shard")
            observed.add(int(m.group(1)))
        if observed!=set(ids):
            raise ValueError("advertised shard directories do not reconcile")
        for n in sorted(ids):
            folder=epoch/f"shard_{n:04d}"
            prefix=f"{epoch.name}/shard_{n:04d}"
            quality=folder/"quality.json"
            eligible_quality=f"{prefix}/quality.json"
            csvs=list(folder.glob("*.csv"))
            if len(csvs)>8 or any(f.is_symlink() or not f.is_file() for f in csvs):
                raise ValueError("malformed original CSV group")
            if eligible_quality not in accepted:
                # A missing source receipt quarantines the entire shard, and
                # this source replay must never claim that CSV bytes were
                # safe to copy on their own.
                if quality.is_file() or quality.is_symlink():
                    raise ValueError("handoff omitted a shard with original receipt")
                quarantined.append(prefix)
                if any(p.startswith(prefix+"/") for p in accepted):
                    raise ValueError("quarantined shard leaked into handoff")
                continue
            if not quality.is_file() or quality.is_symlink():
                raise ValueError("handoff claims a missing quality receipt")
            actual={eligible_quality}
            actual.update(f"{prefix}/{f.name}" for f in csvs)
            declared={p for p in accepted if p.startswith(prefix+"/")}
            if actual!=declared:
                raise ValueError("source shard file set differs from handoff")
            for path in actual:
                if hash_original(root/path)!=accepted[path]:
                    raise ValueError("source file changed after handoff SHA generation")
                replayed+=1;matched.add(path)
    if (active_seen!=1 or matched!=set(accepted)
        or len(quarantined)!=manifest.get("quarantined_source_shards")
        or manifest.get("eligible_shards")!=replayed-len([p for p in matched if p.endswith(".csv")])
        or len(matched)!=manifest["eligible_original_files"]
        or any(q.startswith(active[:16]+"/") for q in quarantined)):
        raise ValueError("source handoff shard counts or quarantine cannot reconcile")
    if manifest.get("missing_original_quality_receipts")!=len(quarantined):
        # This stricter replay only supports quarantine caused by missing
        # original receipts. Non-receipt corruption requires new quarantine
        # semantics, not a silent opt-in to migration.
        raise ValueError("source quarantine not exclusively missing original receipts")
    return {
        "phase":"P1_SOURCE_HANDOFF_INDEPENDENT_BYTE_REPLAY",
        "status":"SOURCE_ONLY_SHA_REPLAYED_DESTINATION_UNVERIFIED",
        "source_epoch_sha256":active,
        "source_file_inventory_sha256":given_hash,
        "source_shards_replayed":manifest["eligible_shards"],
        "source_files_replayed":replayed,
        "quarantined_original_shards":quarantined,
        "archive_status_original_sha256":status_shas,
        "original_status_metadata_sha_separate":True,
        "destination_files_verified":False,
        "migration_performed":False,
        "writer_cutover_authorized":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--handoff",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=replay(a.source,json.loads(a.handoff.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:result[k] for k in (
        "phase","status","source_shards_replayed","source_files_replayed",
        "quarantined_original_shards","source_file_inventory_sha256",
        "destination_files_verified","trade_gate")},ensure_ascii=False))


if __name__=="__main__":
    main()
