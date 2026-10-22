"""Turn bounded live PDF date-proximity observations into quarantined multi-issuer research rows."""
import argparse
import json
from datetime import date, datetime, timezone
from urllib.parse import urlparse
import re
from pathlib import Path
from collector.p3_multi_issuer_research_events import merge_research_ledgers

def adapt_live_pdf_receipts(pdf):
    if pdf.get("phase")!="P3_BOUNDED_RISK_PDF_BYTES_RECAPTURE" or pdf.get("trade_gate")!="BLOCKED" or pdf.get("orders")!=[] or pdf.get("executable_candidates")!=[]:
        raise ValueError("invalid live PDF receipt contract")
    if pdf.get("historical_publication_instant_verified") is not False or pdf.get("actual_issuer_state_verified") is not False:
        raise ValueError("unverified source unexpectedly certified")
    receipts=pdf.get("receipts")
    if not isinstance(receipts,list) or len(receipts)!=pdf.get("attempted"):
        raise ValueError("receipt count mismatch")
    ledgers=[]
    for receipt in receipts:
        code=receipt.get("code")
        market=("SH" if isinstance(code,str) and code.startswith(("600","601","603","605")) else
                "SZ" if isinstance(code,str) and code.startswith(("000","001","002","003")) else None)
        if market not in ("SH","SZ") or not isinstance(code,str):
            raise ValueError("invalid source issuer identity")
        issuer=market.lower()+"."+code
        rows=[]
        if receipt.get("status")=="ORIGINAL_BYTES_CAPTURED_RESEARCH_ONLY" and receipt.get("text_extraction_status")=="TEXT_OBSERVED_NOT_LEGALLY_CLASSIFIED":
            digest=receipt.get("sha256")
            announcement_id=receipt.get("announcement_id")
            pdf_url=receipt.get("pdf_url")
            acquired=receipt.get("retrieved_at_utc")
            if not isinstance(digest,str) or not re.fullmatch(r"[a-f0-9]{64}",digest):
                raise ValueError("invalid PDF SHA")
            if not isinstance(announcement_id,(str,int)) or not str(announcement_id).isdigit():
                raise ValueError("missing original announcement ID")
            if not isinstance(pdf_url,str) or urlparse(pdf_url).scheme!="https" or urlparse(pdf_url).hostname!="static.cninfo.com.cn" or not urlparse(pdf_url).path.startswith("/finalpage/"):
                raise ValueError("invalid provenance URL")
            if not isinstance(acquired,str):
                raise ValueError("missing acquisition timestamp")
            parsed_at=datetime.fromisoformat(acquired)
            if parsed_at.tzinfo is None or parsed_at.utcoffset() is None:
                raise ValueError("acquisition instant must be timezone-aware")
            leads=receipt.get("event_date_proximity_leads_unverified",[])
            if not isinstance(leads,list):raise ValueError("invalid lead list")
            for lead in leads:
                raw_date=lead.get("date_text")
                m=re.fullmatch(r"(20[0-9]{2})\s*年\s*([0-9]{1,2})\s*月\s*([0-9]{1,2})\s*日",raw_date or "")
                if not m:raise ValueError("malformed source date")
                day=date(*(int(n) for n in m.groups())).isoformat()
                flags=lead.get("direction_flags")
                if not isinstance(flags,dict) or not isinstance(lead.get("status"),str):
                    raise ValueError("invalid unverified direction")
                rows.append({"issuer":issuer,"event_kind":"PROXIMITY_"+lead["status"],
                             "mentioned_calendar_date":day,"date_semantics":"ISSUER_STATEMENT",
                             "source_sha256_receipts":[digest],
                             "source_announcement_id":str(announcement_id),
                             "source_pdf_url":pdf_url,
                             "source_retrieved_at_utc":parsed_at.astimezone(timezone.utc).isoformat(),
                             "historical_publication_instant":None,"confirmed_effective_date":None,
                             "tradability_state_asof":None,"eligible_for_historical_universe":False,
                             "research_only":True})
        # Multiple leads can share date+type; retain them only as a single per-day cue.
        unique={}
        for row in rows:
            key=(row["issuer"],row["event_kind"],row["mentioned_calendar_date"],row["source_announcement_id"])
            unique[key]=row
        ledgers.append({"trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
                        "historical_pit_states_verified":False,
                        "confirmed_exchange_effective_event_count":0,
                        "rows":list(unique.values()),"row_count":len(unique)})
    # No candidate is a legitimate empty research result.
    if not ledgers:
        return {"phase":"P3_MULTI_ISSUER_RESEARCH_EVENTS","issuer_count":0,"event_count":0,
                "rows":[],"confirmed_effective_event_count":0,
                "historical_pit_states_verified":False,"trade_gate":"BLOCKED",
                "orders":[],"executable_candidates":[]}
    return merge_research_ledgers(ledgers)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="audit/p3_risk_pdf_hash_receipts.json")
    p.add_argument("--out",default="audit/p3_live_multi_issuer_research.json")
    args=p.parse_args()
    report=adapt_live_pdf_receipts(json.loads(Path(args.source).read_text()))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":report["phase"],"issuer_count":report["issuer_count"],
        "event_count":report["event_count"],"confirmed_effective_event_count":0,
        "trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
