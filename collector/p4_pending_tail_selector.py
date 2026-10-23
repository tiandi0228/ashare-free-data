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
        for item in json.loads(receipt.read_text()).get("results",[]):
            if item.get("status")!="OBSERVED_RESEARCH_ONLY":continue
            filename=item["code"].replace(".","_")+"_tail.csv"
            if item.get("filename")!=filename:raise ValueError("unsafe archive filename")
            if hashlib.sha256((folder/filename).read_bytes()).hexdigest()!=item["sha256"]:
                raise ValueError("archive tail hash mismatch")
            done.add(item["code"])
    tasks=source["tail_backfill_requests"]
    pending=[t for t in tasks if t["code"] not in done]
    chosen=pending[:limit]
    return {"phase":"P4_PENDING_SOURCE_TAIL_SELECTOR","issuer_count":len(tasks),
            "archived_issuers":len(done),"remaining_issuers":len(pending),
            "selected_codes":[x["code"] for x in chosen],
            "selected_issuers":len(chosen),"trade_gate":"BLOCKED"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=select(a.root);Path(a.out).write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":main()
