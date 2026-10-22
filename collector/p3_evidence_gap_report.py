"""Generate an auditable P3 coverage gap report without network calls.

Inputs are explicitly frozen issuer/date lists and independent evidence records.
No historical issuer state is inferred from price bars or missing notices.
"""
import argparse
import json
from pathlib import Path
from collector.p3_historical_evidence_coverage import audit_coverage

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scope",required=True,help="JSON with codes and decision_dates")
    p.add_argument("--observations",required=True,help="JSON array of official-source evidence")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    scope=json.loads(Path(args.scope).read_text(encoding="utf-8"))
    observations=json.loads(Path(args.observations).read_text(encoding="utf-8"))
    if not isinstance(scope,dict) or not isinstance(scope.get("codes"),list) or not isinstance(scope.get("decision_dates"),list):
        raise ValueError("explicit frozen codes and decision_dates are required")
    if len(scope["codes"])>100 or len(scope["decision_dates"])>31:
        raise ValueError("offline report cap exceeded; split work into explicit frozen batches")
    report=audit_coverage(scope["codes"],scope["decision_dates"],observations)
    report["scope_is_full_mainboard"]=False
    report["report_is_live_source_verification"]=False
    report["coverage_ratio"]=f'{report["verified_evidence_cells"]}/{report["required_evidence_cells"]}'
    report["status"]="EVIDENCE_COMPLETE_STILL_TRADE_BLOCKED" if report["complete"] else "EVIDENCE_GAPS_TRADE_BLOCKED"
    report["source_scope_description"]=scope.get("description","bounded explicitly frozen issuer/day study")
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","coverage_ratio","missing_evidence_cells","trade_gate")}))
    return report

if __name__=="__main__":
    main()
