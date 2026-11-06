"""Evidence-bound P2/P3/P4 operational metrics; never a project completion percent.

Only caller-provided original run-scoped JSON observations are interpreted. A
successful CI run or growing research dataset alone cannot certify PIT/OOS
strategy execution or authorize orders.
"""
import argparse
import json
from pathlib import Path

EXPECTED={
    "P2":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
    "P3":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
}
def natural(value,name):
    if type(value) is not int or value<0:
        raise ValueError("invalid nonnegative integer: "+name)
    return value

def safe(record,phase):
    if (not isinstance(record,dict) or record.get("trade_gate")!="BLOCKED"
            or record.get("historical_PIT_verified") is not False
            or record.get("orders")!=[]):
        raise ValueError("untrusted "+phase+" research observation")
    if phase in EXPECTED and record.get("phase")!=EXPECTED[phase]:
        raise ValueError("unexpected "+phase+" research phase")
    return record

def assess(p2,p3,p4,run_ids):
    if (not isinstance(run_ids,dict) or set(run_ids)!={"P2","P3","P4"}
            or any(type(x) is not int or x<=0 for x in run_ids.values())
            or len(set(run_ids.values()))!=3):
        raise ValueError("three distinct exact workflow run identifiers required")
    p2=safe(p2,"P2");p3=safe(p3,"P3");p4=safe(p4,"P4")
    if p4.get("status")!="MODELLED_FEE_BARRIER_GAP_EXPLAINED_NO_BACKTEST":
        raise ValueError("unexpected P4 real source observation")
    complete=natural(p2.get("feature_complete_shards"),"P2 feature_complete_shards")
    gaps=natural(p2.get("observed_with_feature_gaps_shards"),"P2 gap shards")
    observed=natural(p2.get("observed_archived_shards"),"P2 observed archive")
    unobserved=natural(p2.get("unobserved_archived_shards"),"P2 missing")
    if complete+gaps!=observed or unobserved!=0 or observed==0:
        raise ValueError("P2 coverage denominator cannot be reconciled")
    if p2.get("full_archive_evidence_accounted") is not True or p2.get("full_archive_feature_coverage") is not False:
        raise ValueError("P2 unverified research coverage promoted")
    featured=natural(p2.get("feature_issuer_count"),"P2 feature issuers")
    gap_issuers=natural(p2.get("issuer_evidence_gap_count"),"P2 gap issuers")
    all_issuers=natural(p2.get("observed_feature_or_gap_issuers"),"P2 all issuers")
    if featured+gap_issuers!=all_issuers or natural(p2.get("unobserved_issuer_count"),"P2 issuer missing")!=0:
        raise ValueError("P2 issuer counts inconsistent")
    paired=natural(p3.get("deduplicated_research_text_pairs"),"P3 pairs")
    unmatched=natural(p3.get("unpaired_halt_sources_remaining_in_bounded_research"),"P3 unmatched")
    if (p3.get("official_halt_resume_intervals_certified")!=0
            or p3.get("authenticated_first_publication_count")!=0
            or not isinstance(p3.get("text_only_halt_resume_pairs"),list)
            or len(p3["text_only_halt_resume_pairs"])!=paired
            or not isinstance(p3.get("unpaired_original_halt_followups"),list)
            or len(p3["unpaired_original_halt_followups"])!=unmatched):
        raise ValueError("P3 must remain strictly unverified, with counted originals")
    pairs=natural(p4.get("source_verified_price_pairs"),"P4 price proxy pairs")
    passes=natural(p4.get("source_frozen_5pct_reward_risk_passes"),"P4 barrier passes")
    gap=natural(p4.get("gross_2to1_erased_by_modelled_friction"),"P4 friction erasures")
    if (pairs<=0 or passes>pairs or gap>pairs or
            p4.get("trade_authorized") is not False or
            natural(p4.get("broker_trades_verified"),"P4 broker fills")!=0 or
            p4.get("historical_OOS_validated") is not False):
        raise ValueError("P4 price proxy is not authenticated execution")
    return {
        "phase":"P234_RUN_BOUND_EVIDENCE_METRICS",
        "status":"RESEARCH_METRICS_NOT_PROJECT_COMPLETION",
        "source_runs":run_ids,
        "P2":{"feature_complete_shards":complete,"feature_gap_shards":gaps,
              "observed_archived_shards":observed,
              "feature_coverage_pct":round(100*complete/observed,2),
              "feature_issuer_count":featured,"issuer_gap_count":gap_issuers,
              "source_evidence_accounted":True,
              "feature_coverage_is_project_completion":False},
        "P3":{"research_text_pairs":paired,"unpaired_halt_sources":unmatched,
              "certified_halt_resume_intervals":0,
              "authenticated_first_publication_count":0,
              "unpaired_count_is_not_project_completion":True},
        "P4":{"source_proxy_price_pairs":pairs,
              "frozen_5pct_reward_risk_passes":passes,
              "friction_erased_gross_2to1":gap,
              "certified_executable_backtests":0,
              "passing_proxy_rate_is_project_completion":False},
        "engineering_baseline_pct_not_recomputed":{"P2":30,"P3":30,"P4":50},
        "actual_overall_project_progress_pct":None,
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "buy_recommendations_authorized":False
    }

def main():
    p=argparse.ArgumentParser()
    for k in ("p2","p3","p4","out"):p.add_argument("--"+k,required=True)
    for k in ("p2_run","p3_run","p4_run"):p.add_argument("--"+k,required=True,type=int)
    a=p.parse_args()
    report=assess(
        json.loads(Path(a.p2).read_text()),
        json.loads(Path(a.p3).read_text()),
        json.loads(Path(a.p4).read_text()),
        {"P2":a.p2_run,"P3":a.p3_run,"P4":a.p4_run}
    )
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()
