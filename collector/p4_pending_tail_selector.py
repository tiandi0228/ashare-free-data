"""Choose unarchived P4 issuer tasks, verifying permanent receipts and hashes."""
import argparse,hashlib,json
from pathlib import Path
from collector.p4_real_exit_availability import audit

def select(root, limit=8):
    if not 1<=limit<=8:raise ValueError("unbounded selection")
    root=Path(root);source=audit(root)
    done=set()
    for receipt in sorted((root/"p4-tail-backfill").glob("actions-*/backfill_attempt.json")):
        folder=receipt.parent
        report=folder/"independent_verification.json"
        if not report.exists():raise ValueError("archive has unverified tail receipt")
        verified=json.loads(report.read_text())
        if verified.get("trade_gate")!="BLOCKED" or verified.get("archive_merged") is not False:
            raise ValueError("unsafe archive audit")
        verified_items={x["code"]:x for x in verified.get("row_date_details",[])}
        for item in json.loads(receipt.read_text()).get("results",[]):
            if item.get("status")!="OBSERVED_RESEARCH_ONLY":continue
            filename=item["code"].replace(".","_")+"_tail.csv"
            if item.get("filename")!=filename:raise ValueError("unsafe archive filename")
            if hashlib.sha256((folder/filename).read_bytes()).hexdigest()!=item["sha256"]:
                raise ValueError("archive tail hash mismatch")
            detail=verified_items.get(item["code"])
            if not detail or detail.get("rows")!=item.get("rows") or detail.get("restored_exit_date_observations",0)<1:
                raise ValueError("unverified or unmatched archived source tail")
            done.add(item["code"])
    tasks=source["tail_backfill_requests"]
    task_codes={x["code"] for x in tasks}
    if not done.issubset(task_codes):raise ValueError("archived issuer missing from current verified baseline")
    pending=[t for t in tasks if t["code"] not in done]
    chosen=pending[:limit]
    return {"phase":"P4_PENDING_SOURCE_TAIL_SELECTOR","issuer_count":len(tasks),
            "archived_issuers":len(done),"remaining_issuers":len(pending),
            "source_verified_issuers":source["verified_issuers"],
            "source_missing_exit_observations":source["missing_beyond_source_end"],
            "selected_codes":[x["code"] for x in chosen],
            "selected_issuers":len(chosen),"trade_gate":"BLOCKED"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=select(a.root);Path(a.out).write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":main()
