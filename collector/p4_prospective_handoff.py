"""Prospective P3 evidence -> P4 fail-closed boundary, using only current run receipts."""
import argparse
import json
from pathlib import Path

def assess(index, candidate, pdf):
    if not isinstance(index,dict) or not isinstance(candidate,dict) or not isinstance(pdf,dict):
        raise ValueError("invalid audit payload")
    if any(x.get("trade_gate")!="BLOCKED" or x.get("orders")!=[] or x.get("executable_candidates")!=[] for x in (index,candidate,pdf)):
        raise ValueError("unexpected executable receipt")
    pagination=index.get("pagination_complete") is True
    date_ok=(index.get("query_day_time_filter_verified") is True and
             index.get("raw_wrong_day_timestamps")==0 and
             index.get("raw_invalid_timestamps")==0)
    samples=index.get("sample_page_stability_rechecks")
    stable=(isinstance(samples,list) and len(samples)>=3 and
            all(s.get("status")=="MATCH" for s in samples))
    ids=index.get("unique_raw_announcement_ids")
    totals=(type(ids) is int and ids>0 and ids==index.get("reported_total"))
    candidate_consistent=(candidate.get("source_pagination_complete")==pagination and
                          type(candidate.get("candidate_count")) is int and
                          type(pdf.get("candidates_available")) is int and
                          candidate["candidate_count"]==pdf["candidates_available"])
    parsed=(pdf.get("attempted")==pdf.get("successful")==pdf.get("text_extracted_count")
            and pdf.get("text_extraction_failed_count")==0)
    checks={"paged_raw_count":totals,"query_date":date_ok,
            "sample_stability":stable,"pagination":pagination,
            "candidate_lineage":candidate_consistent,"pdf_text":parsed}
    # A successful daily capture is not a valid historical OOS research panel.
    historical_requirements={
        "point_in_time_security_universe":False,
        "historical_ST_halt_delist_daily_states":False,
        "independently_authenticated_publication_instant":False,
        "source_rights_and_reproducible_retention":False,
        "frozen_training_validation_test_split":False,
        "independent_execution_cost_and_fill_replay":False,
    }
    backtest_eligible=all(historical_requirements.values()) and all(checks.values())
    return {"phase":"P3_TO_P4_PROSPECTIVE_HANDOFF",
            "capture_quality_checks":checks,
            "capture_checks_all_passed":all(checks.values()),
            "historical_backtest_input_requirements":historical_requirements,
            "historical_backtest_input_eligible":backtest_eligible,
            "missing_historical_backtest_requirements":[k for k,v in historical_requirements.items() if not v],
            "date":index.get("query_day"),
            "prospective_candidate_count":candidate.get("candidate_count"),
            "pdf_text_count":pdf.get("text_extracted_count"),
            "official_historical_PIT_universe_verified":False,
            "historical_ST_halt_delist_effective_days_verified":False,
            "frozen_out_of_sample_backtest_verified":False,
            "execution_slippage_fee_replay_verified":False,
            "historical_publication_time_authenticated":False,
            "full_market_historical_coverage_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "readiness":"RESEARCH_CAPTURE_ONLY",
            "blocking_reasons":["NO_HISTORICAL_PIT_UNIVERSE",
                                "NO_AUTHENTICATED_HISTORICAL_EFFECTIVE_STATES",
                                "NO_INDEPENDENT_OOS_EXECUTION_VALIDATION"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit-dir",default="audit")
    a=p.parse_args()
    root=Path(a.audit_dir)
    names=("cninfo_announcements.json","p3_title_risk_candidates.json","p3_risk_pdf_hash_receipts.json")
    docs=[json.loads((root/n).read_text("utf-8")) for n in names]
    report=assess(*docs)
    (root/"p3_to_p4_readiness.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":
    main()
