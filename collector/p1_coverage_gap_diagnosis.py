"""Fail-closed P1 frozen-roster coverage and archive gap diagnosis. Research only."""
import argparse,json
from pathlib import Path

def diagnose(plan,ledger,archive):
    if plan.get("source_sha256")!=ledger.get("source_sha256"):
        raise ValueError("mixed roster epochs")
    if ledger.get("trade_gate")!="BLOCKED" or archive.get("trade_gate")!="BLOCKED":
        raise ValueError("unsafe research ledger")
    shards=plan["shards"];count=plan["shard_count"]
    if len(shards)!=count or sorted(s["index"] for s in shards)!=list(range(count)):
        raise ValueError("invalid shard mapping")
    done={x["index"] for x in ledger["completed"]}
    if len(done)!=len(ledger["completed"]) or any(x not in range(count) for x in done):
        raise ValueError("duplicate or invalid completed shards")
    if sum(shards[i]["count"] for i in done)!=ledger["completed_issuers"]:
        raise ValueError("completed issuer count conflict")
    missing=[i for i in range(count) if i not in done]
    if missing!=ledger["pending_shards"] or len(done)!=ledger["completed_shards"]:
        raise ValueError("pending shard ledger conflict")
    if archive["archived_issuers"]>ledger["completed_issuers"]:
        raise ValueError("archive overcounts")
    repair=archive["archive_repair_queue"]
    if repair!=sorted(set(repair)) or any(i not in done for i in repair):
        raise ValueError("invalid archive repair queue")
    if archive["archive_gap_issuers"]!=ledger["completed_issuers"]-archive["archived_issuers"]:
        raise ValueError("archive gap conflict")
    pending_issuers=sum(shards[i]["count"] for i in missing)
    return {"phase":"P1_RESEARCH_GAP_DIAGNOSIS",
            "roster_source_sha256":plan["source_sha256"],
            "total_shards":count,"completed_shards":len(done),
            "pending_shards":len(missing),"completed_issuers":ledger["completed_issuers"],
            "pending_issuers":pending_issuers,
            "archive_gap_issuers":archive["archive_gap_issuers"],
            "archive_repair_shards":repair,
            "next_action":"REPAIR_VERIFIED_ARCHIVE" if repair else ("COLLECT_NEXT_PENDING_SHARD" if missing else "RESEARCH_COVERAGE_COMPLETE"),
            "next_shard_index":repair[0] if repair else (missing[0] if missing else None),
            "research_coverage_pct":round(100*len(done)/count,4),
            "complete_historical_PIT_verified":False,
            "full_market_bars_certified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True);p.add_argument("--ledger",required=True)
    p.add_argument("--archive",required=True);p.add_argument("--out",required=True)
    x=p.parse_args()
    q=diagnose(*[json.loads(Path(v).read_text()) for v in (x.plan,x.ledger,x.archive)])
    out=Path(x.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(q,indent=2)+"\n")
    print(json.dumps(q))
if __name__=="__main__":main()
