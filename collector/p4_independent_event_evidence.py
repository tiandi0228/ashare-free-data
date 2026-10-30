"""Independent P4 event manifest verification against original archived CSVs.
Research integrity only; no fills, orders, returns, or PIT certification.
"""
import argparse,csv,hashlib,json,re,subprocess
from collections import deque
from datetime import date
from decimal import Decimal
from pathlib import Path
from collector.p2_independent_bars import assess

def verify(root,manifest):
    data=json.loads(Path(manifest).read_text())
    if data.get("trade_gate")!="BLOCKED" or data.get("orders")!=[] or data.get("executable_candidates")!=[]:
        raise ValueError("unsafe trading boundary")
    if data.get("returns_computed") is not False or data.get("historical_OOS_validated") is not False:
        raise ValueError("unsupported return certification")
    commit=data.get("archive_commit_sha")
    if commit is not None:
        if not re.fullmatch(r"[0-9a-f]{40}",commit):raise ValueError("invalid source archive commit")
        actual=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
        if actual!=commit:raise ValueError("source archive commit mismatch")
    cutoff=date.fromisoformat(data["cutoff_inclusive"])
    events=data["nonoverlapping_event_evidence"]
    if not isinstance(events,list) or len(events)!=data["nonoverlapping_three_observation_crossing_events"]:
        raise ValueError("manifest count mismatch")
    receipt_paths=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipt_paths:raise ValueError("missing original archive")
    source={}
    for receipt in receipt_paths:
        folder=receipt.parent
        checked=assess(folder)
        for item in checked["details"]:
            code=item["code"]
            raw=(folder/(code.replace(".","_")+".csv")).read_bytes()
            digest=hashlib.sha256(raw).hexdigest()
            # P2 assess independently verifies full CSV schema, counts and SHA. 
            if code in source and source[code][0]!=digest:
                raise ValueError("conflicting originals")
            source[code]=(digest,list(csv.DictReader(raw.decode("utf-8-sig").splitlines())))
    # Independently enumerate the COMPLETE set of eligible events.
    # Checking only listed events lets a truncated/recounted manifest pass.
    # This uses a running 20-close window rather than the generator's
    # per-row full-history sums, so it exercises a distinct calculation path.
    expected=[]
    for code,(digest,rows) in sorted(source.items()):
        last_window_end=-1
        previous_above=None
        window=deque(maxlen=20)
        running_sum=Decimal("0")
        for i,row in enumerate(rows):
            if row["tradestatus"]!="1":
                previous_above=None
                continue
            close=Decimal(row["close"])
            if len(window)==20:
                running_sum-=window[0]
            window.append(close)
            running_sum+=close
            if len(window)<20:
                continue
            above=close*20>running_sum
            crossing=above and previous_above is False
            previous_above=above
            if date.fromisoformat(row["date"])<=cutoff or not crossing:
                continue
            if i<=last_window_end:
                continue
            last_window_end=i+3
            future=rows[i+1:i+4]
            expected.append({
                "issuer":code,
                "source_csv_sha256":digest,
                "signal_completed_date":row["date"],
                "three_future_observed_dates":[x["date"] for x in future],
                "three_future_vendor_tradable":len(future)==3 and all(
                    x["tradestatus"]=="1" for x in future),
                "fill_assumed":False,
            })
    # Match the full event records, not merely claimed counts or membership.
    # This rejects omitted, duplicated, reordered and substituted events.
    if events!=expected:
        raise ValueError("incomplete or altered MA20 event evidence manifest")
    previous={}
    ready=0
    for event in events:
        code=event["issuer"]
        if code not in source:raise ValueError("unknown issuer")
        digest,rows=source[code]
        if digest!=event["source_csv_sha256"]:raise ValueError("event source SHA mismatch")
        dates=[r["date"] for r in rows]
        day=event["signal_completed_date"]
        if date.fromisoformat(day)<=cutoff:raise ValueError("signal crosses training holdout boundary")
        if dates.count(day)!=1:raise ValueError("missing or repeated signal date")
        index=dates.index(day)
        if rows[index]["tradestatus"]!="1":raise ValueError("signal date is not vendor tradable")
        # Verify the crossing independently of the event generator.
        if index==0 or rows[index-1]["tradestatus"]!="1":
            raise ValueError("MA20 crossing requires previous tradable observation")
        def above_ma20(end):
            previous=[Decimal(r["close"]) for r in rows[:end+1] if r["tradestatus"]=="1"]
            if len(previous)<20:raise ValueError("insufficient MA20 history")
            return previous[-1]>sum(previous[-20:])/20
        if above_ma20(index-1) or not above_ma20(index):
            raise ValueError("not a fresh MA20 crossing")
        future=rows[index+1:index+4]
        if [r["date"] for r in future]!=event["three_future_observed_dates"]:
            raise ValueError("forward dates mismatch")
        is_ready=len(future)==3 and all(r["tradestatus"]=="1" for r in future)
        if is_ready!=event["three_future_vendor_tradable"]:raise ValueError("future tradability mismatch")
        if event["fill_assumed"] is not False:raise ValueError("fabricated fill")
        if code in previous and index<=previous[code]:raise ValueError("overlapping or unordered events")
        previous[code]=index+3
        ready+=is_ready
    if ready!=data["nonoverlapping_crossings_with_three_following_vendor_tradable_rows"]:
        raise ValueError("ready event count mismatch")
    return {"independently_verified_events":len(events),"independently_verified_forward_ready":ready,
            "trade_gate":"BLOCKED","orders":[],"returns_computed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--manifest",required=True)
    a=p.parse_args();print(json.dumps(verify(a.root,a.manifest)))
if __name__=="__main__":main()
