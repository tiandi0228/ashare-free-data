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
    observed=set(marker["archived_shards"])
    if len(observed)!=len(marker["archived_shards"]):raise ValueError("duplicate archive entries")
    if not observed.issubset({x["index"] for x in ledger["completed"]}):
        raise ValueError("archive references uncompleted shard")
    archived=0
    legacy_without_receipts=[]
    for idx in sorted(observed):
        part=epoch/f"shard_{idx:04d}"
        expected=plan["shards"][idx]
        manifest=part/"quality.json"
        if not manifest.exists():
            legacy_without_receipts.append(idx)
            continue
        receipt=json.loads(manifest.read_text())
        if receipt["manifest_sha256"]!=expected["sha256"] or receipt["status"]!="OBSERVED_SUBSET_UNVERIFIED" or receipt["trade_gate"]!="BLOCKED":
            raise ValueError("invalid permanent quality receipt")
        if len(receipt["results"])!=expected["count"]:raise ValueError("incomplete archive")
        for row in receipt["results"]:
            data=(part/(row["code"].replace(".","_")+".csv")).read_bytes()
            if hashlib.sha256(data).hexdigest()!=row["sha256"]:raise ValueError("archive CSV hash mismatch")
            archived+=1
    result={"archived_issuers":archived,"ledger_issuers":ledger["completed_issuers"],
            "archive_gap_issuers":ledger["completed_issuers"]-archived,"archive_complete":archived==ledger["completed_issuers"],
            "legacy_shards_without_receipts":legacy_without_receipts,
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
