"""P4 production readiness from independently audited real P1/P3 evidence.

No price strategy simulation can be scored as out-of-sample on incomplete,
retrospectively chosen issuer data. This report is deliberately fail closed.
"""
import argparse
import json
from pathlib import Path
from collector.p3_cross_publisher_replay import audit as audit_p3

REPORTS=Path(__file__).resolve().parents[1]/"reports"
FILENAMES=(
 "p3_600421_two_pdf_event_chain_20261021.json",
 "p3_sse_two_official_original_sha_observed_20261022.json",
 "p3_cninfo_two_pdf_independent_sha_recapture_20261022.json",
 "p3_sse_independent_two_originals_verified_20261022.json",
)
def assess(p1_receipt, p3_receipts):
    p3=audit_p3(*p3_receipts)
    if (p1_receipt.get("phase")!="P3_TWO_CNINFO_ORIGINAL_PDF_REACQUISITION"
        or p1_receipt.get("run_id")!=39703908661):
        raise ValueError("provenance receipt mismatch")
    prerequisites={
        "independent_original_source_sha_replay":p3["independent_replay_SHA_match"],
        "official_historical_mainboard_universe":p3["evidence_layers"]["historical_point_in_time_membership_proven"],
        "historical_asof_publication":p3["historical_publication_instant_verified"],
        "full_historical_ST_halt_delist":p3["complete_historical_daily_status_verified"],
        "permitted_durable_originals":p3["raw_source_durably_archived"] and p3["data_redistribution_licensed"],
        "frozen_OOS_and_execution_validation":p3["evidence_layers"]["P4_out_of_sample_strategy_passed"],
    }
    missing=[k for k,v in prerequisites.items() if v is not True]
    return {
        "phase":"P4_REAL_SOURCE_PREREQUISITE_READINESS",
        "evidence_mode":"FROZEN_REPOSITORY_SNAPSHOT",
        "evidence_report_files":list(FILENAMES),
        "source_receipt_run_id":39703908661,
        "independent_live_source_reverification_in_this_run":False,
        "latest_market_coverage_verified_in_this_run":False,
        "status":"NOT_READY_RESEARCH_ONLY",
        "required_conditions":len(prerequisites),
        "verified_conditions":len(prerequisites)-len(missing),
        "missing_conditions":missing,
        "original_sources_independently_matched":p3["independently_replayed_originals"],
        "full_market_backtest_performed_in_this_audit":False,
        "claimed_positive_return_prediction":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"paid_api_calls":0
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    docs=[json.loads((REPORTS/n).read_text(encoding="utf-8")) for n in FILENAMES]
    receipt=docs[2]
    result=assess(receipt,docs)
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
