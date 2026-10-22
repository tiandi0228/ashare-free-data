"""Reconcile frozen SSE first-party notice with issuer forecast, without backdating observation."""
import argparse,json
from datetime import date
from pathlib import Path
from collector.p3_cross_publisher_replay import audit

def reconcile(chain,sse,pdf_replay,sse_replay):
    checked=audit(chain,sse,pdf_replay,sse_replay)
    pages=sse["pages"]
    if len(pages)!=2 or pages[0].get("event")!="DELIST_DECISION_ONLY" or pages[1].get("event")!="DELIST_EFFECTIVE_DATE_ANNOUNCED":
        raise ValueError("SSE notice sequence changed")
    effective=date.fromisoformat(pages[1]["effective_delist_date"])
    announced=date.fromisoformat(pages[1]["document_date"])
    forecast=date.fromisoformat(checked["cninfo_issuer_forecast_last_trade_day"])
    if not announced<effective or forecast!=announced:
        raise ValueError("announcement / forecast chronology changed")
    if checked["historical_publication_instant_verified"] is not False:
        raise ValueError("PIT state unexpectedly promoted")
    row={"issuer":"sh.600421","event":"EXCHANGE_NOTICE_STATED_DELIST_EFFECTIVE_DATE",
         "effective_date_as_stated_in_observed_official_notice":effective.isoformat(),
         "notice_calendar_date":announced.isoformat(),
         "issuer_forecast_final_trading_date":forecast.isoformat(),
         "official_notice_url":pages[1]["url"],
         "original_sha256":pages[1]["sha256"],
         "original_sha_independently_replayed":True,
         "official_document_observed":True,
         "historically_available_at_notice_date":None,
         "historical_asof_publication_verified":False,
         "historical_daily_tradability_certified":False,
         "usable_for_PIT_backtest":False}
    return {"phase":"P3_EXCHANGE_EVENT_NOTICE_DATE_RECONCILIATION",
            "observed_official_notice_event_count":1,"rows":[row],
            "historical_point_in_time_issuer_state_count":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True);args=ap.parse_args()
    names=("p3_600421_two_pdf_event_chain_20261021.json",
      "p3_sse_two_official_original_sha_observed_20261022.json",
      "p3_cninfo_two_pdf_independent_sha_recapture_20261022.json",
      "p3_sse_independent_two_originals_verified_20261022.json")
    docs=[json.loads((Path("reports")/n).read_text()) for n in names]
    result=reconcile(*docs)
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"observed_official_notice_event_count":1,
                      "historical_point_in_time_issuer_state_count":0,"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
