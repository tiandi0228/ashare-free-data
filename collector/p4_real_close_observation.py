"""Retrospective close-only MA20 observation on real independently verified P2 CSVs.

A bar's close is visible only AFTER that session.  No executable entries,
PIT issuer universe certification, or profitability claims.
"""
import argparse,csv,json
from datetime import date
from pathlib import Path
from collector.p2_independent_bars import assess

def replay(root,cutoff="2025-12-31"):
    split=date.fromisoformat(cutoff)
    reports=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not reports:raise ValueError("empty original archive")
    samples=0;positive=0;issuers=0;skipped=0
    for receipt in reports:
        verified=assess(receipt.parent)
        for detail in verified["details"]:
            issuers+=1
            raw=(receipt.parent/(detail["code"].replace(".","_")+".csv")).read_text(encoding="utf-8-sig")
            # Retain inactive sessions as a hard barrier: never silently forward-fill suspended bars.
            history=[]
            for row in csv.DictReader(raw.splitlines()):
                day=date.fromisoformat(row["date"])
                if row["tradestatus"]!="1":
                    history=[];continue
                close=float(row["close"])
                history.append(close)
                if len(history)>20:history.pop(0)
                if day<=split:continue
                if len(history)<20:
                    skipped+=1;continue
                # Current close is known only after the close on 'day'; do not enter on day.
                samples+=1
                positive+=int(close>sum(history)/20)
    return {"phase":"P4_RETROSPECTIVE_REAL_CLOSE_MA20_OBSERVATION",
            "verified_issuers":issuers,"holdout_observations":samples,
            "close_above_ma20_observations":positive,"insufficient_history_rows":skipped,
            "signal_availability":"AFTER_SESSION_CLOSE_ONLY",
            "same_session_execution_permitted":False,
            "orders_simulated":0,"returns_computed":False,
            "historical_PIT_verified":False,"out_of_sample_performance_validated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True)
    p.add_argument("--cutoff",default="2025-12-31");p.add_argument("--out",required=True)
    a=p.parse_args();r=replay(a.root,a.cutoff)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(r,ensure_ascii=False))
if __name__=="__main__":main()
