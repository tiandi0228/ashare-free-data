"""P0 isolated offline-code acceptance; never claims production/live market readiness."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

MODULES = (
    "tests.test_p0_tencent_quote_probe",
    "tests.test_intraday_minute_coverage",
    "tests.test_intraday_cross_source_audit",
    "tests.test_intraday_snapshot_archive",
)

def evaluate(results):
    if not isinstance(results, list) or len(results) != len(MODULES):
        raise ValueError("P0 evidence list must have exactly four modules")
    if [x.get("module") for x in results] != list(MODULES):
        raise ValueError("noncanonical P0 module inventory")
    accepted=[]
    for x in results:
        if type(x.get("returncode")) is not int or type(x.get("ran_tests")) is not bool or type(x.get("reported_ok")) is not bool:
            raise ValueError("invalid P0 run result")
        accepted.append(x["returncode"] == 0 and x["ran_tests"] and x["reported_ok"])
    return {
        "phase": "P0_OFFLINE_ISOLATED_ACCEPTANCE",
        "status": "SELECTED_OFFLINE_TESTS_PASSED" if all(accepted) else "OFFLINE_TEST_FAILURE",
        "selected_offline_modules_passed": sum(accepted),
        "selected_offline_modules_total": len(MODULES),
        "per_module": [{"module":m, "offline_tests_passed":passed} for m,passed in zip(MODULES,accepted)],
        "historical_development_completion_claim_pct": 100,
        "historical_claim_reverified_as_phase_completion": False,
        "current_complete_P0_phase_acceptance_pct": None,
        "live_quote_freshness_verified": False,
        "live_multiday_continuity_verified": False,
        "real_trading_session_coverage_verified": False,
        "historical_PIT_verified": False,
        "production_ready": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }

def run():
    results=[]
    for module in MODULES:
        p=subprocess.run([sys.executable, "-m", "unittest", "-q", module],
                         text=True, capture_output=True, timeout=120, check=False)
        stderr=p.stderr
        results.append({"module":module, "returncode":p.returncode,
                        "ran_tests":"Ran " in stderr,
                        "reported_ok":"\nOK" in stderr})
    return evaluate(results)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--out",required=True,type=Path)
    args=a.parse_args()
    result=run()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"]!="SELECTED_OFFLINE_TESTS_PASSED":
        raise SystemExit("P0 selected offline acceptance failed; no production claims")

if __name__=="__main__":
    main()
