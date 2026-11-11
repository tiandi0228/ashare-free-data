"""Evidence-backed P2/P3/P4 research scoreboard, explicitly NOT engineering %. 

Only immutable archived report fields with aligned research/blocked guardrails
are used. This cannot certify point-in-time universe, executable backtest or
trading eligibility. An absent or inconsistent report fails closed.
"""
import argparse
import json
from pathlib import Path

PHASE="P234_EVIDENCE_COVERAGE_SCOREBOARD_NOT_ENGINEERING_PERCENT"
P2_PHASE="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
P3_PHASE="P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS"
P4_PHASE="P4_FROZEN_STOP_TARGET_FEE_FLOOR_EXPLANATION"


def _integer(report,key):
    v=report.get(key)
    if type(v) is not int or v<0:
        raise ValueError("invalid or missing counter: "+key)
    return v


def _boundary(report,phase):
    if (not isinstance(report,dict) or report.get("phase")!=phase
        or report.get("trade_gate")!="BLOCKED"
        or report.get("historical_PIT_verified") is not False
        or report.get("orders")!=[]
        or report.get("executable_candidates")!=[]):
        raise ValueError("source report absent, unsafe, or wrong phase")


def _percent(n,d):
    return round(100*n/d,2) if d else None


def scoreboard(p2,p3,p4,source_runs):
    _boundary(p2,P2_PHASE)
    _boundary(p3,P3_PHASE)
    _boundary(p4,P4_PHASE)
    if (p2.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
        or p3.get("official_halt_resume_intervals_certified")!=0
        or p3.get("authenticated_first_publication_count")!=0
        or p4.get("status")!="MODELLED_FEE_BARRIER_GAP_EXPLAINED_NO_BACKTEST"
        or p4.get("historical_OOS_validated") is not False
        or p4.get("strategy_backtest_certified") is not False):
        raise ValueError("source scope or certification changed; re-review required")
    if (not isinstance(source_runs,dict) or set(source_runs)!={"p2","p3","p4"}
        or any(type(v) is not int or v<=0 for v in source_runs.values())
        or len(set(source_runs.values())) != 3):
        raise ValueError("three exact historical run IDs required")
    p2total=_integer(p2,"observed_archived_shards")
    p2complete=_integer(p2,"feature_complete_shards")
    p2gaps=_integer(p2,"observed_with_feature_gaps_shards")
    p2unseen=_integer(p2,"unobserved_archived_shards")
    p2source=_integer(p2,"checkpoint_completed_shards")
    p2issuers=_integer(p2,"observed_feature_or_gap_issuers")
    p2feature=_integer(p2,"feature_issuer_count")
    p2issuer_gaps=_integer(p2,"issuer_evidence_gap_count")
    p2issuer_unseen=_integer(p2,"unobserved_issuer_count")
    if (p2total!=p2complete+p2gaps or p2total+p2unseen!=p2source
        or p2issuers!=p2feature+p2issuer_gaps
        or p2feature>p2issuers
        or p2unseen!=0 or p2issuer_unseen!=0
        or p2.get("full_archive_evidence_accounted") is not True
        or p2.get("full_archive_feature_coverage") is not (p2gaps==0)):
        raise ValueError("unreconciled P2 archive feature coverage")
    pairs=_integer(p3,"deduplicated_research_text_pairs")
    pending=_integer(p3,"unpaired_halt_sources_remaining_in_bounded_research")
    unique=_integer(p3,"unique_resume_pdf_originals_replayed")
    runs=_integer(p3,"archived_resume_runs_replayed")
    if (not isinstance(p3.get("text_only_halt_resume_pairs"),list)
        or not isinstance(p3.get("unpaired_original_halt_followups"),list)
        or len(p3["text_only_halt_resume_pairs"])!=pairs
        or len(p3["unpaired_original_halt_followups"])!=pending):
        raise ValueError("unreconciled P3 original proof pairs")
    count=_integer(p4,"source_verified_price_pairs")
    cash=_integer(p4,"cash_eligible_observation_pairs")
    passed=_integer(p4,"source_frozen_5pct_reward_risk_passes")
    lost=_integer(p4,"gross_2to1_erased_by_modelled_friction")
    if count==0 or not (0<=passed<=cash<=count) or lost>cash-passed:
        raise ValueError("unreconciled P4 theoretical observation counts")
    return {
        "phase":PHASE,
        "source_run_ids":source_runs,
        "p2":{"research_feature_complete_shards":p2complete,
              "research_observed_shards":p2total,
              "research_feature_coverage_pct":_percent(p2complete,p2total),
              "issuer_feature_complete":p2feature,
              "issuer_feature_gaps":p2issuer_gaps,
              "unobserved_archived_shards":p2unseen,
              "strategy_approved":False},
        "p3":{"sha_linked_resume_text_pairs_unverified":pairs,
              "unpaired_halt_source_count":pending,
              "unique_resume_pdf_originals_replayed":unique,
              "archive_runs_replayed":runs,
              "certified_tradability_intervals":0,
              "pit_coverage_pct":None},
        "p4":{"hypothetical_observation_pairs":count,
              "hypothetical_cash_eligible_pairs":cash,
              "frozen_target_net_2to1_model_passes":passed,
              "gross_2to1_erased_by_modelled_friction":lost,
              "net_2to1_pass_pct_of_cash_eligible":_percent(passed,cash),
              "fills_or_broker_trades_certified":0,
              "backtest_certified":False},
        "engineering_completion_pct":{"p2":None,"p3":None,"p4":None},
        "engineering_percentage_not_derived_from_evidence":True,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
        "buy_recommendations_authorized":False,
        "production_ready":False,
        "limitations":[
            "P2_FEATURE_COVERAGE_NOT_STRATEGY_COMPLETION",
            "P3_TEXT_PAIRS_NOT_OFFICIAL_EFFECTIVE_TIME_OR_ASOF_PROOF",
            "P4_VENDOR_PRICE_PAIRS_NOT_EXECUTABLE_FILLS_OR_BACKTEST",
            "SOURCE_RUN_IDS_PIN_EXACT_HISTORICAL_SNAPSHOTS_NOT_LIVE_PROGRESS",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    for x in ("p2","p3","p4"):p.add_argument("--"+x,required=True,type=Path)
    p.add_argument("--p2-run",required=True,type=int)
    p.add_argument("--p3-run",required=True,type=int)
    p.add_argument("--p4-run",required=True,type=int)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    report=scoreboard(*[json.loads(getattr(a,key).read_text())
                         for key in ("p2","p3","p4")],
                     {key:getattr(a,key+"_run") for key in ("p2","p3","p4")})
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":
    main()
