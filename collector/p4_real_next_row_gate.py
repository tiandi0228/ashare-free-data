"""Replay real P2 close observations into next-row research eligibility, never fills.

Next vendor row is not proof of an official exchange session or tradability.
"""
import argparse,csv,json
from datetime import date
from pathlib import Path
from collector.p2_independent_bars import assess

def replay(root,cutoff="2025-12-31"):
    split=date.fromisoformat(cutoff);receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("missing real source")
    counts={"verified_issuers":0,"after_close_ma20_observations":0,
            "next_vendor_row_present":0,"next_vendor_row_active":0,
            "next_vendor_row_suspended":0,"no_next_vendor_row":0}
    for receipt in receipts:
        source=assess(receipt.parent)
        for detail in source["details"]:
            counts["verified_issuers"]+=1
            raw=(receipt.parent/(detail["code"].replace(".","_")+".csv")).read_text(encoding="utf-8-sig")
            rows=list(csv.DictReader(raw.splitlines()));history=[]
            for i,row in enumerate(rows):
                if row["tradestatus"]!="1":history=[];continue
                day=date.fromisoformat(row["date"]);history.append(float(row["close"]))
                if len(history)>20:history.pop(0)
                if day<=split or len(history)<20 or history[-1]<=sum(history)/20:continue
                counts["after_close_ma20_observations"]+=1
                if i+1==len(rows):
                    counts["no_next_vendor_row"]+=1;continue
                following=rows[i+1]
                if date.fromisoformat(following["date"])<=day:raise ValueError("non-increasing vendor dates")
                counts["next_vendor_row_present"]+=1
                if following["tradestatus"]=="1":counts["next_vendor_row_active"]+=1
                else:counts["next_vendor_row_suspended"]+=1
    if counts["after_close_ma20_observations"]!=counts["next_vendor_row_present"]+counts["no_next_vendor_row"]:
        raise ValueError("chronological accounting mismatch")
    if counts["next_vendor_row_present"]!=counts["next_vendor_row_active"]+counts["next_vendor_row_suspended"]:
        raise ValueError("vendor status accounting mismatch")
    return {"phase":"P4_REAL_NEXT_ROW_RESEARCH_ELIGIBILITY",**counts,
            "next_vendor_row_is_official_trading_calendar":False,
            "vendor_status_is_official_halt_certification":False,
            "orders_simulated":0,"fills_verified":0,"returns_computed":False,
            "historical_PIT_verified":False,"out_of_sample_performance_validated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True)
    p.add_argument("--cutoff",default="2025-12-31");p.add_argument("--out",required=True)
    a=p.parse_args();r=replay(a.root,a.cutoff);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(r,ensure_ascii=False))
if __name__=="__main__":main()
