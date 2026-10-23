"""Research-only MA20 signal availability and next-three observed bars audit.

Uses independently P2-validated archived vendor CSV. No fills, PnL,
tradability certification, or out-of-sample strategy validation.
"""
import argparse,csv,hashlib,json
from decimal import Decimal
from pathlib import Path
from collector.p2_independent_bars import assess

def audit(root,cutoff="2025-12-31"):
    from datetime import date
    boundary=date.fromisoformat(cutoff)
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("missing P2 originals")
    seen={}
    issuer_count=signals=forward_ready=0
    signal_issuers=set();forward_issuers=set();censored_end=0;blocked_vendor_status=0
    for p in receipts:
        receipt=assess(p.parent)
        for item in receipt["details"]:
            code=item["code"]
            raw=(p.parent/(code.replace(".","_")+".csv")).read_bytes()
            digest=hashlib.sha256(raw).hexdigest()
            if code in seen:
                if seen[code]!=digest:raise ValueError("conflicting original issuer bytes")
                continue
            seen[code]=digest
            issuer_count+=1
            rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            # Only vendor-tradable past observations enter the rolling MA.
            for i,row in enumerate(rows):
                if date.fromisoformat(row["date"])<=boundary or row["tradestatus"]!="1":
                    continue
                prior=[Decimal(x["close"]) for x in rows[:i+1] if x["tradestatus"]=="1"]
                if len(prior)<20:continue
                # Signal formed after this day's close, never at the open.
                if prior[-1]<=sum(prior[-20:])/20:continue
                signals+=1
                signal_issuers.add(code)
                # The following three *observed* vendor rows must all be tradable.
                future=rows[i+1:i+4]
                if len(future)<3:
                    censored_end+=1
                elif not all(x["tradestatus"]=="1" for x in future):
                    blocked_vendor_status+=1
                else:
                    forward_ready+=1
                    forward_issuers.add(code)
    return {"phase":"P4_REAL_VENDOR_MA20_FORWARD_OBSERVATION",
            "cutoff_inclusive":boundary.isoformat(),"independently_p2_checked_issuers":issuer_count,
            "post_cutoff_ma20_observations":signals,
            "issuers_with_ma20_observations":len(signal_issuers),
            "issuers_with_three_following_vendor_tradable_rows":len(forward_issuers),
            "observations_censored_at_archive_end":censored_end,
            "observations_blocked_by_vendor_status":blocked_vendor_status,
            "three_following_vendor_tradable_rows":forward_ready,
            "entry_fills_assumed":0,"returns_computed":False,
            "historical_PIT_verified":False,"historical_OOS_validated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True)
    ap.add_argument("--cutoff",default="2025-12-31")
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    result=audit(a.root,a.cutoff)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":main()
