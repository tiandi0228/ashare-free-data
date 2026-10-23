"""Audit unique restored exit-date observations across immutable tail archives.

Counts exact target occurrences, not CSV lines or successful issuers.
Research-only: neither OHLC presence nor vendor status establishes a fill.
"""
import argparse,csv,hashlib,json
from pathlib import Path
from collector.p2_independent_bars import assess
from collector.p4_curated_session_exit import research_exit
from collector.p4_real_exit_availability import audit

def reconcile(root):
    root=Path(root);baseline=audit(root)
    needed={}
    for receipt in sorted(root.glob("*/shard_*/quality.json")):
        for item in assess(receipt.parent)["details"]:
            code=item["code"]
            path=receipt.parent/(code.replace(".","_")+".csv")
            rows=list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
            last=rows[-1]["date"]
            for row in rows:
                if row["date"]<="2025-12-31" or row["tradestatus"]!="1":continue
                try:target=research_exit(row["date"])["candidate_earlier_exit"]
                except ValueError:continue
                if target>last:needed.setdefault(code,[]).append(target)
    if sum(map(len,needed.values()))!=baseline["missing_beyond_source_end"]:
        raise ValueError("baseline mismatch")
    restored={};seen=0;archived_files=0
    for receipt in sorted((root/"p4-tail-backfill").glob("actions-*/backfill_attempt.json")):
        manifest=json.loads(receipt.read_text())
        folder=receipt.parent
        verification=json.loads((folder/"independent_verification.json").read_text())
        if manifest.get("trade_gate")!="BLOCKED" or verification.get("trade_gate")!="BLOCKED":
            raise ValueError("unsafe archived tail")
        for item in manifest.get("results",[]):
            if item["status"]!="OBSERVED_RESEARCH_ONLY":continue
            code=item["code"]
            if code not in needed:raise ValueError("out-of-baseline issuer")
            filename=code.replace(".","_")+"_tail.csv"
            if item.get("filename")!=filename:raise ValueError("unexpected filename")
            raw=(folder/filename).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item["sha256"]:raise ValueError("tail hash mismatch")
            rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            if len(rows)!=item["rows"]:raise ValueError("tail rows mismatch")
            for row in rows:
                if row["code"]!=code:raise ValueError("issuer identity mismatch")
                key=(code,row["date"])
                old=restored.get(key)
                if old is not None and old!=row:raise ValueError("conflicting duplicate archived quote")
                restored[key]=row
            archived_files+=1;seen+=len(rows)
    active=suspended=found=0
    for code,targets in needed.items():
        for day in targets:
            row=restored.get((code,day))
            if row is None:continue
            found+=1
            if row["tradestatus"]=="1":active+=1
            elif row["tradestatus"]=="0":suspended+=1
            else:raise ValueError("unknown vendor status")
    return {"phase":"P4_CUMULATIVE_EXACT_EXIT_RECONCILIATION",
        "baseline_issuers_with_missing_exits":len(needed),
        "baseline_missing_exit_observations":sum(map(len,needed.values())),
        "archived_tail_csv_files":archived_files,"archived_tail_rows_including_duplicates":seen,
        "unique_archived_issuer_dates":len(restored),
        "restored_exit_observations":found,"restored_vendor_active":active,
        "restored_vendor_suspended":suspended,
        "remaining_exit_observations":sum(map(len,needed.values()))-found,
        "trade_gate":"BLOCKED","orders":[],"fills_verified":0,
        "official_halt_verified":False,"historical_PIT_verified":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=reconcile(a.root);Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(r))
if __name__=="__main__":main()
