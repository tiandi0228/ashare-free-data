"""Conservative P2/P3/P4 offline engineering acceptance baseline; never a trade gate."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PHASES = {
 "P2": ("archive_screen_contract","indicator_coverage","sector_point_in_time","short_strategy","medium_strategy","costs","anti_lookahead","out_of_sample","risk_reward","full_universe_acceptance"),
 "P3": ("proof_gap_triage_contract","source_original_hashes","historical_first_publication","halt_resume_intervals","historical_st_status","delist_status","historical_pit_roster","calendar_pit","official_audit_replay","complete_pit_acceptance"),
 "P4": ("synthetic_t1_contract","partial_fill_audit","friday_exit_audit","official_calendar","limit_band_history","order_book_uncertainty","fee_risk_budget","strategy_fill_provenance","out_of_sample_execution","end_to_end_acceptance"),
}
TESTS = {
 "P2": ("archive_screen_contract","collector/p2_real_archive_research_screen.py","tests.test_p2_real_archive_research_screen"),
 "P3": ("proof_gap_triage_contract","collector/p3_proof_gap_triage.py","tests.test_p3_proof_gap_triage"),
 "P4": ("synthetic_t1_contract","collector/p4_synthetic_t1_execution_kernel.py","tests.test_p4_synthetic_t1_execution_kernel"),
}

def audit(root, manifest, commit, run_tests=False):
    if not isinstance(commit,str) or not re.fullmatch(r"[0-9a-f]{40}",commit):
        raise ValueError("exact 40-character source commit SHA required")
    if (not isinstance(manifest,dict)
        or manifest.get("schema_version")!=1
        or manifest.get("mode")!="CONSERVATIVE_ENGINEERING_ACCEPTANCE_ONLY"
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("historical_PIT_verified") is not False
        or set(manifest.get("phases",{})) != set(PHASES)):
        raise ValueError("unsafe or inconsistent milestone manifest")
    outputs={}
    for phase,ids in PHASES.items():
        declared=manifest["phases"][phase]
        if (not isinstance(declared,list) or len(declared)!=10
            or any(not isinstance(x,dict) for x in declared)
            or [x.get("id") for x in declared]!=list(ids)
            or any(type(x.get("weight")) is not int or x["weight"]!=10 for x in declared)):
            raise ValueError("frozen denominator modified for "+phase)
        gate,source,module=TESTS[phase]
        rows=[]
        for entry in declared:
            passed=False
            evidence=None
            if run_tests and entry["id"]==gate and (root/source).is_file():
                test=subprocess.run([sys.executable,"-m","unittest","-q",module],
                                    cwd=root,capture_output=True,text=True,timeout=120)
                passed=(test.returncode==0 and "Ran " in test.stderr and "OK" in test.stderr)
                if passed:
                    evidence={"source_code":source,"test_module":module,"source_commit":commit,
                              "verification":"OFFLINE_UNITTEST_PASSED_IN_THIS_RUN"}
            rows.append({"id":entry["id"],"weight":10,"passed":passed,
                         "evidence":evidence,
                         "status":"VERIFIED_OFFLINE" if passed else "NOT_ADMITTED"})
        weight=sum(row["weight"] for row in rows if row["passed"])
        outputs[phase]={"engineering_acceptance_baseline_pct":weight if run_tests else None,
                        "accepted_weight":weight if run_tests else 0,"total_weight":100,
                        "criteria":rows,"data_certification_pct":None,
                        "formal_trading_ready":False}
    return {"phase":"STOCKMATE_P2_P4_ENGINEERING_BASELINE",
            "source_commit":commit,"status":"OFFLINE_ACCEPTANCE_ONLY",
            "tests_executed":bool(run_tests),"stages":outputs,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[],"recommendations":[],
            "caveat":"BASELINE_IS_NOT_OVERALL_PROJECT_COMPLETION_OR_TRADING_CERTIFICATION"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--manifest",type=Path,default=Path("progress_manifest.json"))
    p.add_argument("--commit",required=True)
    p.add_argument("--run-tests",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=audit(args.root.resolve(),json.loads(args.manifest.read_text()),args.commit,args.run_tests)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({key:value["engineering_acceptance_baseline_pct"] for key,value in result["stages"].items()}))

if __name__=="__main__":
    main()
