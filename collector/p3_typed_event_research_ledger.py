"""Typed research-only historical event rows from independently checked frozen 600421 evidence."""
import argparse
import json
from datetime import date
from pathlib import Path
from collector.p3_two_pdf_event_chain import combine

EXPECTED_KINDS={
    "ISSUER_STATED_RESUMPTION_DATE":("stated_date","ISSUER_STATEMENT"),
    "ISSUER_FORECAST_FINAL_TRADING_DATE":("forecast","ISSUER_FORECAST"),
    "EXCHANGE_EFFECTIVE_DELIST_DATE_AUDIT_REFERENCE_ONLY":("reference_effective_date","UNVERIFIED_REFERENCE"),
}
def normalize(chain):
    if chain.get("status")!="TWO_ISSUER_DOCUMENT_SHA_RECEIPTS_PIT_BLOCKED" or chain.get("trade_gate")!="BLOCKED" or chain.get("orders")!=[]:
        raise ValueError("historical evidence not admissible")
    if chain.get("issuer")!="sh.600421" or chain.get("historical_release_timestamp_verified") is not False:
        raise ValueError("unverified issuer or time")
    originals=chain.get("issuer_pdf_sha_receipts")
    if not isinstance(originals,list) or len(originals)!=2 or any(not isinstance(s,str) or len(s)!=64 for s in originals):
        raise ValueError("invalid original SHA receipts")
    events=chain.get("event_types")
    if not isinstance(events,list) or len(events)!=3 or {e.get("type") for e in events}!=set(EXPECTED_KINDS):
        raise ValueError("unexpected event list")
    rows=[]
    for e in events:
        kind=e["type"]
        field,certainty=EXPECTED_KINDS[kind]
        event_day=date.fromisoformat(e[field]).isoformat()
        # A reference to an exchange event isn't an exchange original.
        if kind=="EXCHANGE_EFFECTIVE_DELIST_DATE_AUDIT_REFERENCE_ONLY" and (
            e.get("first_party_original_observed_in_runner") is not False or
            e.get("exchange_original_sha256") is not None):
            raise ValueError("unexpected exchange evidence")
        if kind=="ISSUER_STATED_RESUMPTION_DATE" and e.get("actual_exchange_tradability_verified") is not False:
            raise ValueError("resumption falsely verified")
        if kind=="ISSUER_FORECAST_FINAL_TRADING_DATE" and e.get("is_effective_exchange_delist") is not False:
            raise ValueError("forecast falsely promoted")
        rows.append({"issuer":chain["issuer"],"event_kind":kind,
                     "mentioned_calendar_date":event_day,"date_semantics":certainty,
                     "source_sha256_receipts":originals if certainty!="UNVERIFIED_REFERENCE" else [],
                     "historical_publication_instant":None,
                     "confirmed_effective_date":None,"tradability_state_asof":None,
                     "eligible_for_historical_universe":False,"research_only":True})
    return {"phase":"P3_TYPED_HISTORICAL_EVENT_RESEARCH_LEDGER",
            "decision_date":chain.get("decision_date"),
            "rows":rows,"row_count":len(rows),
            "confirmed_exchange_effective_event_count":0,
            "historical_pit_states_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--asof",default="2026-06-22")
    a=p.parse_args()
    r=Path("reports")
    early=json.loads((r/"p3_cninfo_600421_early_20261021.json").read_text())
    later=json.loads((r/"p3_cninfo_600421_disclosure_pdf_20261021.json").read_text())
    out=normalize(combine(early,later,a.asof))
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":out["phase"],"row_count":out["row_count"],
                     "confirmed_exchange_effective_event_count":0,"trade_gate":"BLOCKED"}))
if __name__=="__main__":
    main()
