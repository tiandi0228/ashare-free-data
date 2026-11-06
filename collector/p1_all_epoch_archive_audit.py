"""Read-only all-epoch original CSV audit before copying into a private archive.

No source writes; historical PIT, source authenticity, and trading remain unverified.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

EPOCH=re.compile(r"[0-9a-f]{16}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
SHARD=re.compile(r"shard_([0-9]{4})\Z")
ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""):
            h.update(part)
    return h.hexdigest()


def examine(root):
    root=Path(root)
    report={"phase":"P1_ALL_EPOCH_SOURCE_ARCHIVE_READINESS",
            "status":"SOURCE_ARCHIVE_INCOMPLETE",
            "epoch_count":0,"advertised_shards":0,
            "verified_original_shards":0,"verified_original_csv_files":0,
            "unlisted_original_receipts":0,"invalid_originals":0,
            "issue_sample":[],"issue_count":0,
            "source_archive_sha_verified":False,
            "destination_mirror_verified":False,
            "writer_cutover_authorized":False,"historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    def issue(reason,path):
        report["issue_count"]+=1
        if len(report["issue_sample"])<40:
            report["issue_sample"].append({"reason":reason,"path":str(path)})
    if not root.is_dir():
        issue("source directory missing",root)
        return report
    for item in root.rglob("*"):
        if ".git" in item.relative_to(root).parts:
            continue
        if item.is_symlink():
            issue("unsafe symlink",item.relative_to(root))
    for epoch in sorted(p for p in root.iterdir() if p.is_dir() and p.name!=".git"):
        if EPOCH.fullmatch(epoch.name) is None:
            issue("invalid archive epoch directory",epoch.name)
            continue
        report["epoch_count"]+=1
        status_path=epoch/"archive_status.json"
        if not status_path.is_file():
            issue("archive status missing",status_path.relative_to(root))
            continue
        try:
            status=json.loads(status_path.read_text())
            raw=status["archived_shards"]
            sha=status["source_sha256"]
            if (not isinstance(raw,list) or
                any(type(v) is not int or not 0<=v<=9999 for v in raw) or
                len(raw)!=len(set(raw)) or
                not isinstance(sha,str) or SHA.fullmatch(sha) is None or
                not sha.startswith(epoch.name) or
                status.get("trade_gate")!="BLOCKED"):
                raise ValueError("invalid status fields")
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as err:
            issue("invalid archive status: "+str(err),status_path.relative_to(root))
            continue
        expected=set(raw)
        report["advertised_shards"]+=len(expected)
        for folder in epoch.glob("shard_*"):
            m=SHARD.fullmatch(folder.name)
            if m is None or not folder.is_dir():
                issue("invalid shard directory",folder.relative_to(root))
            elif int(m.group(1)) not in expected:
                report["unlisted_original_receipts"]+=1
                issue("unlisted original shard",folder.relative_to(root))
        for i in sorted(expected):
            folder=epoch/f"shard_{i:04d}"
            receipt_path=folder/"quality.json"
            if not receipt_path.is_file():
                issue("status advertises missing shard receipt",receipt_path.relative_to(root))
                report["invalid_originals"]+=1
                continue
            try:
                receipt=json.loads(receipt_path.read_text())
                rows=receipt["results"]
                if (receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or
                    receipt.get("trade_gate")!="BLOCKED" or
                    receipt.get("orders")!=[] or
                    receipt.get("historical_point_in_time_universe_verified") is not False or
                    type(receipt.get("issuer_count")) is not int or
                    not 1<=receipt["issuer_count"]<=8 or
                    not isinstance(rows,list) or
                    len(rows)!=receipt["issuer_count"]):
                    raise ValueError("invalid original receipt")
                seen=set()
                for row in rows:
                    code=row["code"]
                    if (not isinstance(code,str) or ISSUER.fullmatch(code) is None or
                        code in seen or row.get("status")!="OBSERVED_UNVERIFIED" or
                        not isinstance(row.get("sha256"),str) or
                        SHA.fullmatch(row["sha256"]) is None):
                        raise ValueError("invalid original issuer evidence")
                    seen.add(code)
                    csv=folder/(code.replace(".","_")+".csv")
                    if not csv.is_file() or digest(csv)!=row["sha256"]:
                        raise ValueError("missing or SHA-invalid original CSV: "+csv.name)
                actual={p.name for p in folder.iterdir() if p.is_file()}
                expected_files={"quality.json"}|{code.replace(".","_")+".csv" for code in seen}
                if actual!=expected_files:
                    raise ValueError("unlisted or missing original shard file")
                report["verified_original_shards"]+=1
                report["verified_original_csv_files"]+=len(rows)
            except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as err:
                report["invalid_originals"]+=1
                issue(str(err),receipt_path.relative_to(root))
    if report["epoch_count"]==0:
        issue("no archive epochs",root)
    report["source_archive_sha_verified"]=(
        report["issue_count"]==0 and
        report["advertised_shards"]==report["verified_original_shards"])
    if report["source_archive_sha_verified"]:
        report["status"]="ALL_EPOCH_SOURCE_ORIGINALS_SHA_VERIFIED"
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    r=examine(args.source)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))


if __name__=="__main__":
    main()
