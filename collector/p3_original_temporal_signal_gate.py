"""Fail-closed temporal gate for original announcement receipts and historical signals.

A current download of an old PDF verifies retrospective content, not contemporaneous
availability. A date printed in a file is not a verified acquisition timestamp.
"""
import argparse,json
from datetime import date,datetime,timezone
from pathlib import Path

def classify(receipt, signal_date):
    if not isinstance(receipt,dict) or not isinstance(receipt.get("sources"),list):
        raise ValueError("missing source receipt collection")
    day=date.fromisoformat(signal_date)
    accepted=[]
    rejected=[]
    for source in receipt["sources"]:
        if not isinstance(source,dict) or not isinstance(source.get("source_id"),str):
            raise ValueError("invalid source entry")
        why=[]
        if source.get("original_bytes_verified") is not True or source.get("listing_day_text_verified") is not True:
            why.append("ORIGINAL_AND_CONTENT_NOT_VERIFIED")
        observed=source.get("acquired_at_utc")
        if not isinstance(observed,str):
            why.append("MISSING_ACQUISITION_TIME")
        else:
            dt=datetime.fromisoformat(observed.replace("Z","+00:00"))
            if dt.tzinfo is None:
                raise ValueError("naive source acquisition timestamp")
            if dt.astimezone(timezone.utc).date()>day:
                why.append("ACQUIRED_AFTER_SIGNAL_DAY")
        if source.get("historic_PIT_publication_verified") is not True:
            why.append("HISTORICAL_PUBLICATION_INSTANT_UNVERIFIED")
        if source.get("historical_ipo_notice_verified") is not True:
            why.append("HISTORICAL_ISSUER_MEMBERSHIP_NOT_CERTIFIED")
        item={"source_id":source["source_id"],"reasons":why}
        (rejected if why else accepted).append(item)
    return {"phase":"P3_SOURCE_TEMPORAL_ELIGIBILITY_GATE",
            "signal_date":signal_date,"evaluated_sources":len(receipt["sources"]),
            "eligible_sources":accepted,"ineligible_sources":rejected,
            "source_eligible_for_historical_signal":bool(accepted),
            "historical_full_market_universe_certified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",required=True);p.add_argument("--signal-date",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=classify(json.loads(Path(a.receipt).read_text()),a.signal_date)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10))
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
