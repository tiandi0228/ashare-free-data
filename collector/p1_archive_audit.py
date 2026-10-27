"""Independent frozen-roster CSV archive completeness audit (NO TRADES)."""
import argparse, hashlib, json
from pathlib import Path

def audit(plan, ledger, root):
    if ledger["source_sha256"]!=plan["source_sha256"] or ledger["trade_gate"]!="BLOCKED":
        raise ValueError("ledger belongs to different roster or opens trade")
    epoch=Path(root)/plan["source_sha256"][:16]
    marker=json.loads((epoch/"archive_status.json").read_text())
    if marker["source_sha256"]!=plan["source_sha256"] or marker["trade_gate"]!="BLOCKED":
        raise ValueError("invalid archive marker")
    entries=marker.get("archived_shards")
    if (not isinstance(entries,list) or
        any(type(index) is not int or not 0<=index<len(plan["shards"]) for index in entries)):
        raise ValueError("invalid archive shard indices")
    observed=set(entries)
    if len(observed)!=len(entries):raise ValueError("duplicate archive entries")
    if not observed.issubset({x["index"] for x in ledger["completed"]}):
        raise ValueError("archive references uncompleted shard")
    archived=0
    ledger_receipts={item["index"]:item for item in ledger["completed"]}
    legacy_without_receipts=[]
    for idx in sorted(observed):
        part=epoch/f"shard_{idx:04d}"
        expected=plan["shards"][idx]
        manifest=part/"quality.json"
        if not manifest.exists():
            legacy_without_receipts.append(idx)
            continue
        receipt=json.loads(manifest.read_text())
        canonical=hashlib.sha256(json.dumps(receipt,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if canonical!=ledger_receipts[idx].get("receipt_sha256"):
            raise ValueError("archived receipt does not match immutable ledger evidence")
        if receipt["manifest_sha256"]!=expected["sha256"] or receipt["status"]!="OBSERVED_SUBSET_UNVERIFIED" or receipt["trade_gate"]!="BLOCKED":
            raise ValueError("invalid permanent quality receipt")
        results=receipt["results"]
        if not isinstance(results,list) or len(results)!=expected["count"]:
            raise ValueError("incomplete archive")
        codes=[row.get("code") for row in results if isinstance(row,dict)]
        if len(codes)!=len(results) or any(not isinstance(code,str) for code in codes) or len(set(codes))!=len(codes):
            raise ValueError("duplicate or invalid archived issuer codes")
        if receipt.get("issuer_count") is not None and receipt["issuer_count"]!=expected["count"]:
            raise ValueError("archived issuer count mismatch")
        for row in results:
            data=(part/(row["code"].replace(".","_")+".csv")).read_bytes()
            if hashlib.sha256(data).hexdigest()!=row["sha256"]:raise ValueError("archive CSV hash mismatch")
            archived+=1
    completed={x["index"] for x in ledger["completed"]}
    missing_shards=sorted(completed-observed)
    repair_shards=sorted(set(missing_shards)|set(legacy_without_receipts))
    result={"source_sha256":plan["source_sha256"],"archived_issuers":archived,"ledger_issuers":ledger["completed_issuers"],
            "archive_gap_issuers":ledger["completed_issuers"]-archived,"archive_complete":archived==ledger["completed_issuers"],
            "legacy_shards_without_receipts":legacy_without_receipts,
            "unarchived_shards":missing_shards,"archive_repair_queue":repair_shards,
            "repair_shard_count":len(repair_shards),
            "trade_gate":"BLOCKED","historical_PIT_verified":False}
    if result["archive_gap_issuers"]<0:raise ValueError("overreported archive")
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--ledger",required=True)
    ap.add_argument("--root",required=True)
    ap.add_argument("--out",required=True)
    x=ap.parse_args()
    report=audit(json.loads(Path(x.plan).read_text()),json.loads(Path(x.ledger).read_text()),x.root)
    Path(x.out).write_text(json.dumps(report,indent=2)+chr(10))
    print(json.dumps(report))
if __name__=="__main__":main()
