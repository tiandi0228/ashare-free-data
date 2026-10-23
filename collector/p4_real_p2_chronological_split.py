"""P4 evidence-only chronological split of independently verified real P2 archive.

No signals, trade simulation, return claims, or historical PIT certification.
"""
import argparse,csv,hashlib,json
from datetime import date
from pathlib import Path
from collector.p2_independent_bars import assess

def audit(root,cutoff):
    cutoff=date.fromisoformat(cutoff)
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("no durable original receipts")
    counts={"train_rows":0,"holdout_rows":0,"issuers_with_holdout":0,"verified_issuers":0,"issuers_with_both_periods":0}
    digests=[];seen={};per_issuer=[];identical_duplicate_receipts=0
    for p in receipts:
        verified=assess(p.parent)
        for item in verified["details"]:
            code=item["code"]
            raw=(p.parent/(code.replace(".","_")+".csv")).read_bytes()
            digest=hashlib.sha256(raw).hexdigest()
            if code in seen:
                if seen[code]!=digest:raise ValueError("conflicting duplicate issuer across original shards")
                identical_duplicate_receipts+=1
                continue
            seen[code]=digest
            digests.append({"issuer":code,"sha256":digest})
            dates=[date.fromisoformat(r["date"]) for r in csv.DictReader(raw.decode("utf-8-sig").splitlines())]
            train=sum(day<=cutoff for day in dates);holdout=len(dates)-train
            counts["train_rows"]+=train;counts["holdout_rows"]+=holdout
            counts["issuers_with_holdout"]+=int(holdout>0)
            counts["verified_issuers"]+=1
            counts["issuers_with_both_periods"]+=int(train>0 and holdout>0)
            per_issuer.append({"issuer":code,"train_rows":train,"holdout_rows":holdout,
                               "train_last":max((d.isoformat() for d in dates if d<=cutoff),default=None),
                               "holdout_first":min((d.isoformat() for d in dates if d>cutoff),default=None)})
    if counts["train_rows"]==0 or counts["holdout_rows"]==0:raise ValueError("both research periods require actual bars")
    if counts["issuers_with_both_periods"]==0:
        raise ValueError("no independently verified issuer crosses research cutoff")
    for row in per_issuer:
        if row["train_last"] is not None and row["holdout_first"] is not None and row["train_last"]>=row["holdout_first"]:
            raise ValueError("issuer time overlap")
    return {"phase":"P4_REAL_P2_CHRONOLOGICAL_RESEARCH_SPLIT","cutoff_inclusive":cutoff.isoformat(),
            **counts,"identical_duplicate_receipts_skipped":identical_duplicate_receipts,"per_issuer_split":per_issuer,"source_csv_sha256":digests,"split_time_order_verified":True,"issuer_level_overlap_count":0,
            "signals_evaluated":0,"out_of_sample_performance_validated":False,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True)
    p.add_argument("--cutoff",default="2025-12-31");p.add_argument("--out",required=True)
    a=p.parse_args();r=audit(a.root,a.cutoff)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="source_csv_sha256"}))
if __name__=="__main__":main()
