"""Real archived vendor bars versus curated SSE session successors (research only)."""
import argparse,csv,json
from collections import Counter
from pathlib import Path
from collector.p2_independent_bars import assess
from collector.p4_curated_session_exit import sessions_between

def audit(root,cutoff="2025-12-31"):
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("no P2 source receipts")
    counts=Counter();examples=[]
    for receipt in receipts:
        verified=assess(receipt.parent)
        for item in verified["details"]:
            counts["verified_issuers"]+=1
            path=receipt.parent/(item["code"].replace(".","_")+".csv")
            rows=list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
            for i,row in enumerate(rows):
                day=row["date"]
                if day<=cutoff or row["tradestatus"]!="1":continue
                counts["holdout_active_rows"]+=1
                if i+1==len(rows):
                    counts["last_vendor_row_no_successor"]+=1;continue
                successor=rows[i+1]["date"]
                possible=sessions_between(day,successor)
                if not possible or possible[0]!=day:raise ValueError("vendor active date excluded by curated sessions")
                if len(possible)<2:raise ValueError("same curated session for distinct rows")
                gap=len(possible)-1
                counts["vendor_next_row_present"]+=1
                if gap==1:counts["next_row_is_next_curated_session"]+=1
                else:
                    counts["vendor_row_skips_curated_sessions"]+=1
                    if len(examples)<20:examples.append({"code":item["code"],"day":day,"next_vendor_day":successor,"curated_session_gap":gap})
                if rows[i+1]["tradestatus"]=="0":counts["successor_vendor_suspended"]+=1
    if counts["holdout_active_rows"]!=counts["last_vendor_row_no_successor"]+counts["vendor_next_row_present"]:
        raise ValueError("source accounting mismatch")
    return {"phase":"P4_REAL_VENDOR_CURATED_SESSION_JOIN",**counts,
            "skipped_session_examples":examples,
            "curated_sse_calendar_is_full_official_calendar":False,
            "szse_calendar_authenticated":False,
            "issuer_halts_independently_authenticated":False,
            "trades_simulated":0,"fills_verified":0,"returns_computed":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=audit(a.root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="skipped_session_examples"},ensure_ascii=False))
if __name__=="__main__":main()
