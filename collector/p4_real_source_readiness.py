"""P4 production readiness from independently audited real P1/P3 evidence.

No price strategy simulation can be scored as out-of-sample on incomplete,
retrospectively chosen issuer data. This report is deliberately fail closed.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path
from collector.p3_cross_publisher_replay import audit as audit_p3

REPORTS=Path(__file__).resolve().parents[1]/"reports"
FILENAMES=(
 "p3_600421_two_pdf_event_chain_20261021.json",
 "p3_sse_two_official_original_sha_observed_20261022.json",
 "p3_cninfo_two_pdf_independent_sha_recapture_20261022.json",
 "p3_sse_independent_two_originals_verified_20261022.json",
)
def snapshot_age(as_of_date):
    """Filename date is metadata only, never publication or live verification."""
    today=date.fromisoformat(as_of_date)
    days=[]
    for name in FILENAMES:
        match=re.search(r"_(\d{8})\.json$", name)
        if not match:
            raise ValueError("missing snapshot filename date")
        stamp=match.group(1)
        captured=date.fromisoformat(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}")
        if captured>today:
            raise ValueError("snapshot filename date is in the future")
        days.append(captured)
    return {"snapshot_latest_filename_date":max(days).isoformat(),
            "snapshot_oldest_filename_date":min(days).isoformat(),
            "snapshot_latest_filename_age_days":(today-max(days)).days,
            "snapshot_date_is_source_publication_proof":False}

def assess(p1_receipt, p3_receipts, as_of_date=None):
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
    as_of_date=as_of_date or date.today().isoformat()
    age=snapshot_age(as_of_date)
    # A same-day filename does not certify that a live source was rechecked.
    live_current=False
    blocking_reasons=list(missing)
    if not live_current:
        blocking_reasons.append("NO_INDEPENDENT_LIVE_SOURCE_REVERIFICATION")
    return {
        **age,
        "assessment_as_of_date":as_of_date,
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
        "current_evidence_eligible":live_current,
        "live_readiness_blocking_reasons":blocking_reasons,
        "production_readiness_eligible":False,
        "original_sources_independently_matched":p3["independently_replayed_originals"],
        "full_market_backtest_performed_in_this_audit":False,
        "claimed_positive_return_prediction":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"paid_api_calls":0
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True)
    ap.add_argument("--as-of-date",default=date.today().isoformat())
    args=ap.parse_args()
    docs=[json.loads((REPORTS/n).read_text(encoding="utf-8")) for n in FILENAMES]
    receipt=docs[2]
    result=assess(receipt,docs,as_of_date=args.as_of_date)
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
