"""Join observed official primary evidence into one auditable historical risk inventory.

The inventory is retrospective and must not be interpreted as point-in-time
universe/status completeness. No claim of tradability is made.
"""
import argparse,json
from pathlib import Path
from collector.p3_exchange_notice_event_reconciliation import reconcile

def build(ipo_receipt,exchange_notice):
    sources=ipo_receipt.get("sources")
    if not isinstance(sources,list):
        raise ValueError("IPO source receipt unavailable")
    ipo=next((s for s in sources if s.get("source_id")=="cninfo_2025_ipo_original"),None)
    if (not ipo or ipo.get("original_bytes_verified") is not True or
        ipo.get("listing_day_text_verified") is not True or
        ipo.get("published_day")!="2025-05-16" or
        ipo.get("historic_PIT_publication_verified") is not False):
        raise ValueError("IPO original content evidence not complete")
    if (exchange_notice.get("phase")!="P3_EXCHANGE_EVENT_NOTICE_DATE_RECONCILIATION" or
        exchange_notice.get("historical_point_in_time_issuer_state_count")!=0):
        raise ValueError("exchange notice research only")
    rows=exchange_notice.get("rows",[])
    if len(rows)!=1 or rows[0].get("issuer")!="sh.600421" or rows[0].get("original_sha_independently_replayed") is not True:
        raise ValueError("official delist original not independently verified")
    r=rows[0]
    events=[
      {"issuer":"sh.603014","kind":"IPO_LISTING",
       "effective_date_as_stated":"2025-05-19","source_published_day_claim":"2025-05-16",
       "original_sha256":ipo["sha256"],"source_url":ipo["url"],
       "original_bytes_verified":True,"official_content_verified":True,
       "historically_available_at_effective_day":False,
       "issuer_day_state_PIT_eligible":False},
      {"issuer":"sh.600421","kind":"DELIST_EFFECTIVE",
       "effective_date_as_stated":r["effective_date_as_stated_in_observed_official_notice"],
       "source_published_day_claim":r["notice_calendar_date"],
       "original_sha256":r["original_sha256"],"source_url":r["official_notice_url"],
       "original_bytes_verified":True,"official_content_verified":True,
       "historically_available_at_effective_day":False,
       "issuer_day_state_PIT_eligible":False}]
    return {"phase":"P3_TWO_ISSUER_OFFICIAL_EVENT_RETROSPECTIVE_INVENTORY",
       "independent_issuers":2,"retrospective_official_events":2,
       "historical_PIT_eligible_events":0,"events":events,
       "historical_ST_halt_delist_full_coverage":False,
       "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ipo",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    names=("p3_600421_two_pdf_event_chain_20261021.json",
      "p3_sse_two_official_original_sha_observed_20261022.json",
      "p3_cninfo_two_pdf_independent_sha_recapture_20261022.json",
      "p3_sse_independent_two_originals_verified_20261022.json")
    exchange=reconcile(*(json.loads((Path("reports")/n).read_text()) for n in names))
    result=build(json.loads(Path(a.ipo).read_text()),exchange)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10))
    print(json.dumps({"phase":result["phase"],"independent_issuers":2,
         "retrospective_official_events":2,"historical_PIT_eligible_events":0,
         "trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
