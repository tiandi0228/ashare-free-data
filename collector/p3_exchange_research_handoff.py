"""Combine observed SSE effective-date notice and multi-issuer research cues without PIT promotion."""
import argparse
import json
from pathlib import Path
from collector.p3_exchange_notice_event_reconciliation import reconcile
from collector.p3_typed_event_research_ledger import normalize
from collector.p3_multi_issuer_research_events import merge_research_ledgers
from collector.p3_two_pdf_event_chain import combine

def assemble(issuer_ledger, exchange_notice):
    merged=merge_research_ledgers([issuer_ledger])
    if exchange_notice.get("phase")!="P3_EXCHANGE_EVENT_NOTICE_DATE_RECONCILIATION" or exchange_notice.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid exchange notice")
    events=exchange_notice.get("rows")
    if not isinstance(events,list) or len(events)!=1 or exchange_notice.get("observed_official_notice_event_count")!=1:
        raise ValueError("unexpected exchange event evidence")
    e=events[0]
    if e.get("issuer")!="sh.600421" or e.get("official_document_observed") is not True or e.get("original_sha_independently_replayed") is not True:
        raise ValueError("exchange provenance mismatch")
    if e.get("historical_asof_publication_verified") is not False or e.get("usable_for_PIT_backtest") is not False:
        raise ValueError("historical availability falsely certified")
    if e.get("historically_available_at_notice_date") is not None:
        raise ValueError("historical availability cannot be inferred")
    if e.get("effective_date_as_stated_in_observed_official_notice")!="2026-06-26":
        raise ValueError("unexpected exchange effective date")
    if not any(r["issuer"]==e["issuer"] for r in merged["rows"]):
        raise ValueError("exchange notice missing issuer in ledger")
    return {"phase":"P3_RECONCILED_RESEARCH_NOTICE_LEDGER",
            "issuer_count":merged["issuer_count"],"issuer_event_cues":merged["event_count"],
            "observed_exchange_effective_date_notices":1,
            "exchange_notice_evidence":[dict(e)],
            "historically_authenticated_effective_dates":0,
            "historical_PIT_state_eligible":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);args=p.parse_args()
    root=Path("reports")
    load=lambda name:json.loads((root/name).read_text())
    early=load("p3_cninfo_600421_early_20261021.json")
    late=load("p3_cninfo_600421_disclosure_pdf_20261021.json")
    source=normalize(combine(early,late,"2026-06-22"))
    cninfo=load("p3_600421_two_pdf_event_chain_20261021.json")
    sse=load("p3_sse_two_official_original_sha_observed_20261022.json")
    pdf_replay=load("p3_cninfo_two_pdf_independent_sha_recapture_20261022.json")
    sse_replay=load("p3_sse_independent_two_originals_verified_20261022.json")
    output=assemble(source,reconcile(cninfo,sse,pdf_replay,sse_replay))
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":output["phase"],"observed_exchange_effective_date_notices":1,
                     "historically_authenticated_effective_dates":0,"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
