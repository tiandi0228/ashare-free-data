"""Independent cross-run audit of the 16 real free-Baostock shard artifacts."""
import argparse,csv,hashlib,json,math
from collections import Counter
from datetime import date
from pathlib import Path

EXPECTED_MANIFEST_SHA="a369c66bbb8289ed418fdec7fd3cc4e5200ad0214916aea4cfbf46a40af68af0"
def audit(root, expected_manifest_sha=EXPECTED_MANIFEST_SHA):
    root=Path(root)
    docs=list(root.rglob("quality.json"))
    if len(docs)!=16:
        raise ValueError(f"expected 16 actual source receipts; got {len(docs)}")
    seen_batches=set();seen_issuers=set();total_rows=0;active=0;halted=0
    per_issuer={};calendars=Counter()
    for file in docs:
        q=json.loads(file.read_text())
        batch=q.get("batch_index",0)
        if type(batch) is not int or batch not in range(16) or batch in seen_batches:
            raise ValueError("duplicate or invalid batch")
        seen_batches.add(batch)
        if (q.get("manifest_sha256")!=expected_manifest_sha or
            q.get("source_status")!="EIGHT_FREE_ISSUER_HISTORIES_OBSERVED_RESEARCH_ONLY" or
            q.get("issuer_count")!=8 or len(q.get("issuer_receipts",[]))!=8 or
            q.get("shard_manifest_count")!=128 or
            q.get("trade_gate")!="BLOCKED" or q.get("orders")!=[] or
            q.get("executable_candidates")!=[] or
            q.get("historical_PIT_verified") is not False):
            raise ValueError("source receipt contract mismatch")
        manifest=file.parent/"manifest.txt"
        raw_manifest=manifest.read_bytes()
        if hashlib.sha256(raw_manifest).hexdigest()!=expected_manifest_sha:
            raise ValueError("manifest byte hash mismatch")
        codes=raw_manifest.decode().splitlines()
        if len(codes)!=128 or len(set(codes))!=128:
            raise ValueError("invalid frozen manifest")
        intended=codes[batch*8:(batch+1)*8]
        actual=[e.get("code") for e in q["issuer_receipts"]]
        if actual!=intended:
            raise ValueError("issuer missing or moved between batches")
        for entry in q["issuer_receipts"]:
            code=entry["code"]
            if code in seen_issuers:
                raise ValueError("duplicate issuer across batches")
            seen_issuers.add(code)
            raw=(file.parent/(code.replace(".","_")+".csv")).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=entry.get("sha256"):
                raise ValueError("source CSV SHA mismatch")
            records=list(csv.reader(raw.decode().splitlines()))
            if len(records)-1!=entry["rows"]:
                raise ValueError("source CSV row count mismatch")
            rows=records[1:]
            if records[0]!=["date","code","open","high","low","close","volume","amount","adjustflag","tradestatus"]:
                raise ValueError("source column mismatch")
            dates=[r[0] for r in rows]
            if any(len(r)!=10 or r[1]!=code for r in rows):
                raise ValueError("source row identity/shape mismatch")
            if dates!=sorted(set(dates)):
                raise ValueError("duplicate or unordered issuer dates")
            for r in rows:
                date.fromisoformat(r[0])
                if r[9]=="1":
                    try:
                        op,hi,lo,cl,vol,amt=[float(r[i]) for i in (2,3,4,5,6,7)]
                    except (ValueError,TypeError) as exc:
                        raise ValueError("invalid active bar number") from exc
                    if (not all(map(math.isfinite,(op,hi,lo,cl,vol,amt))) or
                        min(op,hi,lo,cl)<=0 or hi<max(op,cl) or lo>min(op,cl) or vol<0 or amt<0):
                        raise ValueError("invalid active OHLC values")
                elif r[9]!="0":
                    raise ValueError("invalid vendor trading status")
                calendars[r[0]]+=1
            per_issuer[code]=set(dates)
            trade=sum(r[9]=="1" for r in records[1:])
            suspend=sum(r[9]=="0" for r in records[1:])
            if trade!=entry["valid_active_bars"] or suspend!=entry["suspended_placeholder_rows"]:
                raise ValueError("source status count mismatch")
            total_rows+=len(records)-1;active+=trade;halted+=suspend
    # Peer-observed sessions are a diagnostic, not an official trading calendar.
    peer_days={d for d,n in calendars.items() if n>=64}
    missing_peer={code:len(peer_days-days) for code,days in per_issuer.items()}
    missing_detail=[]
    buckets={"BEFORE_FIRST_VENDOR_ROW":0,"BETWEEN_VENDOR_ROWS":0,"AFTER_LAST_VENDOR_ROW":0}
    for code, days in sorted(per_issuer.items()):
        first,last=min(days),max(days)
        for day in sorted(peer_days-days):
            classification=("BEFORE_FIRST_VENDOR_ROW" if day<first else
                            "AFTER_LAST_VENDOR_ROW" if day>last else
                            "BETWEEN_VENDOR_ROWS")
            buckets[classification]+=1
            missing_detail.append({"code":code,"date":day,"position":classification,
                                   "reason_authenticated":False})
    if sum(buckets.values())!=sum(missing_peer.values()):
        raise ValueError("missing-day diagnostic accounting mismatch")
    report={"phase":"P1_128_LIVE_CROSS_RUN_INDEPENDENT_AUDIT",
            "manifest_sha256":expected_manifest_sha,
            "verified_batches":len(seen_batches),"verified_unique_issuers":len(seen_issuers),
            "historical_rows":total_rows,
            "distinct_vendor_observed_days":len(calendars),
            "majority_peer_observed_days":len(peer_days),
            "issuer_peer_missing_day_counts":missing_peer,
            "total_peer_missing_issuer_days":sum(missing_peer.values()),
            "missing_peer_date_position_counts":buckets,
            "missing_peer_date_details":missing_detail,
            "first_last_vendor_row_is_listing_lifecycle_proof":False,
            "inside_span_gap_is_confirmed_source_error":False,
            "peer_calendar_is_official":False,"active_status_rows":active,
            "suspended_status_rows":halted,
            "complete_128_research_source_replay":len(seen_issuers)==128,
            "official_PIT_universe_verified":False,
            "historical_ST_halt_delist_complete":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    if seen_batches!=set(range(16)) or active+halted!=total_rows:
        raise ValueError("coverage/accounting incomplete")
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    p.add_argument("--manifest-sha",default=EXPECTED_MANIFEST_SHA)
    args=p.parse_args()
    result=audit(args.input,expected_manifest_sha=args.manifest_sha)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
