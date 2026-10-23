"""Offline audit of captured SSE HTML with strict original-byte checksum verification.

Historical cached notices never certify PIT or exchange trading calendars.
"""
import argparse,hashlib,json
from pathlib import Path
from collector.p4_sse_notice_body_dates import inspect

def replay(root):
    root=Path(root);p=json.loads((root/"manifest.json").read_text())
    if p.get("trade_gate")!="BLOCKED" or p.get("expected_count")!=3:
        raise ValueError("unsafe or incomplete original manifest")
    records=[]
    for receipt in p["receipts"]:
        if receipt.get("status")!="CAPTURED_OFFICIAL_HOST_CONTENT_UNVERIFIED":
            raise ValueError("original SSE snapshot unavailable")
        year=receipt["year"];name=f"sse_{year}.html"
        if receipt.get("filename")!=name:raise ValueError("invalid snapshot path")
        raw=(root/name).read_bytes()
        if not raw or hashlib.sha256(raw).hexdigest()!=receipt["sha256"]:
            raise ValueError("original HTML integrity failure")
        parsed=inspect(year,raw)
        records.append({"year":year,"sha256":receipt["sha256"],
                        "missing_dates":parsed["ranges_missing_textual_dates"],
                        "unpaired_ranges":parsed["ranges_without_adjacent_closure_phrase"]})
    if len({i["year"] for i in records})!=3:raise ValueError("incomplete distinct years")
    return {"phase":"P4_SSE_OFFLINE_ORIGINAL_REPLAY","source_years":len(records),
            "range_date_presence_complete":all(not x["missing_dates"] for x in records),
            "paired_range_phrase_complete":all(not x["unpaired_ranges"] for x in records),
            "records":records,"historical_exchange_calendar_authenticated":False,
            "trade_gate":"BLOCKED","orders":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=replay(a.root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="records"}))
if __name__=="__main__":main()
