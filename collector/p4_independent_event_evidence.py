"""Independent P4 event manifest verification against original archived CSVs.
Research integrity only; no fills, orders, returns, or PIT certification.
"""
import argparse,csv,hashlib,json
from pathlib import Path

def verify(root,manifest):
    data=json.loads(Path(manifest).read_text())
    if data.get("trade_gate")!="BLOCKED" or data.get("orders")!=[] or data.get("executable_candidates")!=[]:
        raise ValueError("unsafe trading boundary")
    if data.get("returns_computed") is not False or data.get("historical_OOS_validated") is not False:
        raise ValueError("unsupported return certification")
    events=data["nonoverlapping_event_evidence"]
    if not isinstance(events,list) or len(events)!=data["nonoverlapping_three_observation_crossing_events"]:
        raise ValueError("manifest count mismatch")
    receipt_paths=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipt_paths:raise ValueError("missing original archive")
    source={}
    for receipt in receipt_paths:
        folder=receipt.parent
        for item in json.loads(receipt.read_text())["results"]:
            code=item["code"]
            raw=(folder/(code.replace(".","_")+".csv")).read_bytes()
            digest=hashlib.sha256(raw).hexdigest()
            if digest!=item["sha256"]:raise ValueError("original receipt CSV hash mismatch")
            if code in source and source[code][0]!=digest:
                raise ValueError("conflicting originals")
            source[code]=(digest,list(csv.DictReader(raw.decode("utf-8-sig").splitlines())))
    previous={}
    ready=0
    for event in events:
        code=event["issuer"]
        if code not in source:raise ValueError("unknown issuer")
        digest,rows=source[code]
        if digest!=event["source_csv_sha256"]:raise ValueError("event source SHA mismatch")
        dates=[r["date"] for r in rows]
        day=event["signal_completed_date"]
        if dates.count(day)!=1:raise ValueError("missing or repeated signal date")
        index=dates.index(day)
        if rows[index]["tradestatus"]!="1":raise ValueError("signal date is not vendor tradable")
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
