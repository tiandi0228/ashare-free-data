"""Research-only MA20 signal availability and next-three observed bars audit.

Uses independently P2-validated archived vendor CSV. No fills, PnL,
tradability certification, or out-of-sample strategy validation.
"""
import argparse,csv,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from collector.p2_independent_bars import assess

def audit(root,cutoff="2025-12-31",archive_commit=None):
    if archive_commit is not None and not re.fullmatch(r"[0-9a-f]{40}",archive_commit):
        raise ValueError("invalid archived git commit")
    from datetime import date
    boundary=date.fromisoformat(cutoff)
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("missing P2 originals")
    seen={}
    event_manifest=[]
    issuer_count=signals=forward_ready=0
    crossing_events=0;crossing_forward_ready=0;crossing_issuers=set()
    nonoverlap_crossings=0;nonoverlap_forward_ready=0
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
            previous_above=None
            last_selected_window_end=-1
            for i,row in enumerate(rows):
                if row["tradestatus"]!="1":
                    previous_above=None
                    continue
                prior=[Decimal(x["close"]) for x in rows[:i+1] if x["tradestatus"]=="1"]
                if len(prior)<20:continue
                above=prior[-1]>sum(prior[-20:])/20
                crossing=above and previous_above is False
                previous_above=above
                if date.fromisoformat(row["date"])<=boundary or not above:continue
                # Condition formed after close, never at open.
                nonoverlap_crossing=crossing and i>last_selected_window_end
                if crossing:
                    crossing_events+=1
                    crossing_issuers.add(code)
                if nonoverlap_crossing:
                    nonoverlap_crossings+=1
                    last_selected_window_end=i+3
                signals+=1
                signal_issuers.add(code)
                # The following three *observed* vendor rows must all be tradable.
                future=rows[i+1:i+4]
                if nonoverlap_crossing:
                    event_manifest.append({"issuer":code,"source_csv_sha256":digest,
                                           "signal_completed_date":row["date"],
                                           "three_future_observed_dates":[x["date"] for x in future],
                                           "three_future_vendor_tradable":len(future)==3 and all(x["tradestatus"]=="1" for x in future),
                                           "fill_assumed":False})
                if len(future)<3:
                    censored_end+=1
                elif not all(x["tradestatus"]=="1" for x in future):
                    blocked_vendor_status+=1
                else:
                    forward_ready+=1
                    forward_issuers.add(code)
                    if crossing:crossing_forward_ready+=1
                    if nonoverlap_crossing:nonoverlap_forward_ready+=1
    event_manifest.sort(key=lambda e:(e["issuer"],e["signal_completed_date"]))
    if len(event_manifest)!=nonoverlap_crossings:
        raise ValueError("nonoverlapping event manifest count mismatch")
    if sum(e["three_future_vendor_tradable"] for e in event_manifest)!=nonoverlap_forward_ready:
        raise ValueError("nonoverlapping forward evidence count mismatch")
    return {"phase":"P4_REAL_VENDOR_MA20_FORWARD_OBSERVATION",
            "cutoff_inclusive":boundary.isoformat(),"archive_commit_sha":archive_commit,"independently_p2_checked_issuers":issuer_count,
            "post_cutoff_ma20_observations":signals,
            "fresh_ma20_crossing_events":crossing_events,
            "nonoverlapping_three_observation_crossing_events":nonoverlap_crossings,
            "nonoverlapping_event_evidence":event_manifest,
            "nonoverlapping_crossings_with_three_following_vendor_tradable_rows":nonoverlap_forward_ready,
            "issuers_with_fresh_crossing_events":len(crossing_issuers),
            "fresh_crossing_events_with_three_following_vendor_tradable_rows":crossing_forward_ready,
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
    ap.add_argument("--archive-commit")
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    result=audit(a.root,a.cutoff,a.archive_commit)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    summary={k:v for k,v in result.items() if k!="nonoverlapping_event_evidence"}
    summary["event_evidence_entries_written"]=len(result["nonoverlapping_event_evidence"])
    print(json.dumps(summary))
if __name__=="__main__":main()
