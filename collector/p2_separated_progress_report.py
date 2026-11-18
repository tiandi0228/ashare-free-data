"""Separate P2 historical feature coverage from offline engineering acceptance.

Historical conversation/report counters are intentionally not current verified
ledger counters. Only exact-source, independently replayed evidence can be
marked as current. Absent evidence means unknown, never regression to 30%.
"""
import json
from datetime import date

PHASE = "P2_FEATURE_VS_ENGINEERING_PROGRESS_SEPARATION"


def summarize(engineering, historical, current=None):
    if (not isinstance(engineering, dict)
        or engineering.get("phase") != "STOCKMATE_P2_P4_ENGINEERING_BASELINE"
        or engineering.get("trade_gate") != "BLOCKED"
        or engineering.get("historical_PIT_verified") is not False
        or engineering.get("orders") != []
        or engineering.get("executable_candidates") != []
        or engineering.get("tests_executed") is not True):
        raise ValueError("unsafe offline engineering baseline")
    stage = engineering.get("stages", {}).get("P2")
    if not isinstance(stage, dict):
        raise ValueError("missing P2 engineering stage")
    rows = stage.get("criteria")
    if (not isinstance(rows, list) or len(rows) != 10
        or type(stage.get("engineering_acceptance_baseline_pct")) is not int):
        raise ValueError("invalid fixed offline denominator")
    passed = sum(x.get("passed") is True for x in rows)
    if (passed * 10 != stage["engineering_acceptance_baseline_pct"]
        or any(x.get("weight") != 10 for x in rows)):
        raise ValueError("offline engineering stage incoherent")
    if not isinstance(historical, list) or len(historical) > 20 or not historical:
        raise ValueError("historical record set missing")
    seen = set()
    observed = []
    for row in historical:
        if not isinstance(row, dict) or row.get("kind") != "PREVIOUSLY_REPORTED_NOT_REPLAYED_THIS_RUN":
            raise ValueError("untrusted historical progress label")
        day = row.get("reported_day")
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("invalid historical day")
        n, d = row.get("feature_complete_shards"), row.get("observed_shards")
        if (type(n) is not int or type(d) is not int or not 0 <= n <= d <= 400
            or (day,n,d) in seen):
            raise ValueError("invalid or duplicate historical count")
        seen.add((day,n,d))
        observed.append({
            "reported_day": day,
            "feature_complete_shards": n,
            "observed_shards": d,
            "feature_coverage_pct": round(100*n/d,2) if d else None,
            "evidence_status": "HISTORICAL_REPORTED_UNREPLAYED",
            "current_source_epoch_confirmed": False,
        })
    observed.sort(key=lambda r:(r["reported_day"],r["observed_shards"]))
    current_result = None
    if current is not None:
        if (not isinstance(current, dict)
            or current.get("phase") != "P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
            or current.get("status") != "DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            or current.get("trade_gate") != "BLOCKED"
            or current.get("historical_PIT_verified") is not False
            or current.get("orders") != []
            or current.get("executable_candidates") != []
            or current.get("coverage_certified_for_trading") is not False
            or current.get("original_csv_sha_replay_verified_in_this_run") is not True):
            raise ValueError("current feature report lacks independent original replay attestation")
        n,d = current.get("feature_complete_shards"),current.get("observed_archived_shards")
        gap = current.get("observed_with_feature_gaps_shards")
        if (type(n) is not int or type(d) is not int or type(gap) is not int
            or d <= 0 or n + gap != d):
            raise ValueError("current feature evidence counter mismatch")
        current_result = {
            "feature_complete_shards": n,
            "observed_shards": d,
            "feature_coverage_pct": round(100*n/d,2),
            "status": "CURRENT_ORIGINAL_REPLAY_VERIFIED",
        }
    return {
        "phase":PHASE,
        "P2_offline_engineering_criteria_passed": passed,
        "P2_offline_engineering_total":10,
        "P2_offline_engineering_pct":passed * 10,
        "P2_historical_feature_observations":observed,
        "P2_latest_historical_report":observed[-1],
        "P2_current_feature_coverage":current_result,
        "P2_overall_project_completion_pct":None,
        "P2_progress_regression_proven":False,
        "current_evidence_missing_is_not_regression":True,
        "official_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser()
    p.add_argument("--engineering",required=True,type=Path)
    p.add_argument("--historical",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=summarize(json.loads(a.engineering.read_text()),
                     json.loads(a.historical.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "P2_offline_engineering_pct":result["P2_offline_engineering_pct"],
        "P2_latest_historical_report":result["P2_latest_historical_report"],
        "P2_current_feature_coverage":result["P2_current_feature_coverage"],
        "P2_overall_project_completion_pct":None,
        "trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
