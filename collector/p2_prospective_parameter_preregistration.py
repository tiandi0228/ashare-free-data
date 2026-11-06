"""Prospective P2 model-parameter pre-registration candidate, NO certification.

Hashes an exact, typed fixed hypothesis and validation boundaries. A SHA
created now cannot establish that a model was frozen before historical
validation dates. GitHub run timestamps and data availability require separate
attestation, so outputs cannot certify historical OOS strategy performance.
"""
import argparse,hashlib,json,re
from datetime import date,datetime,timezone
from pathlib import Path

PHASE="P2_PROSPECTIVE_RESEARCH_PARAMETER_PREREGISTRATION"
SHA40=re.compile(r"[a-f0-9]{40}\Z")
ALLOWED_HYPOTHESES={
  "MA20_CROSS_UPWARD_COMPLETED_DAILY_BAR_RESEARCH_ONLY":{
    "feature":"close_crosses_above_ma20_on_completed_day",
    "lookback_sessions":20,
    "holding_sessions":3,
    "signal_asof":"AFTER_DAILY_BAR_COMPLETION",
    "entry_model":"NEXT_SESSION_OPEN_PROXY_NOT_FILL",
    "exit_model":"THIRD_FOLLOWING_CLOSE_PROXY_NOT_FILL",
    "cost_basis":"NO_EXECUTION_RETURNS_CERTIFIED"
  }
}
def _date(raw):
    if not isinstance(raw,str):raise ValueError("date text expected")
    d=date.fromisoformat(raw)
    if d.isoformat()!=raw:raise ValueError("noncanonical date")
    return d

def register(*,source_commit,hypothesis,validation_start,validation_end,
             evidence_created_at_utc,fold_source_sha256):
    base={"phase":PHASE,"status":"REJECTED",
          "historical_PIT_verified":False,"historical_OOS_validated":False,
          "parameters_frozen_before_historical_holdout_verified":False,
          "prospective_freeze_externally_attested":False,
          "strategy_returns_computed":False,
          "order_execution_authenticated":False,
          "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
          "actionable_buy_signals":[]}
    def reject(reason):return dict(base,reason=reason)
    try:
        if (not isinstance(source_commit,str) or not SHA40.fullmatch(source_commit)
            or not isinstance(fold_source_sha256,str) or
            not re.fullmatch("[a-f0-9]{64}",fold_source_sha256)):
            return reject("SOURCE_IDENTITY_NOT_PINNED")
        if hypothesis not in ALLOWED_HYPOTHESES:
            return reject("HYPOTHESIS_NOT_APPROVED_OR_CHANGED")
        vstart=_date(validation_start)
        vend=_date(validation_end)
        if vend<=vstart:
            return reject("VALIDATION_WINDOW_INVALID")
        if (not isinstance(evidence_created_at_utc,str) or
            not evidence_created_at_utc.endswith("Z")):
            return reject("NOT_CANONICAL_UTC_INSTANT")
        frozen=datetime.fromisoformat(evidence_created_at_utc.replace("Z","+00:00"))
        if (frozen.tzinfo!=timezone.utc or
            frozen.isoformat(timespec="seconds").replace("+00:00","Z")!=evidence_created_at_utc):
            return reject("NOT_CANONICAL_UTC_INSTANT")
        if frozen.date()>=vstart:
            return dict(base,status="RETROSPECTIVE_WINDOW_CANNOT_BE_FROZEN_AFTER_START",
                        reason="PRE_REGISTRATION_TIMESTAMP_NOT_BEFORE_VALIDATION",
                        evidence_created_at_utc=evidence_created_at_utc,
                        validation_start=vstart.isoformat())
        fixed={"schema_version":1,"hypothesis":hypothesis,
               "parameters":ALLOWED_HYPOTHESES[hypothesis],
               "validation_start":vstart.isoformat(),
               "validation_end":vend.isoformat(),
               "source_commit_sha":source_commit,
               "fold_source_sha256":fold_source_sha256,
               "evidence_created_at_utc":evidence_created_at_utc,
               "trade_gate":"BLOCKED"}
        canonical=json.dumps(fixed,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        return dict(base,status="PROSPECTIVE_CANDIDATE_NOT_EXTERNAL_TIME_ATTESTATION",
                    parameter_candidate_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
                    candidate=fixed,
                    missing_evidence=[
                      "INDEPENDENT_GITHUB_RUN_CREATION_TIMESTAMP_AND_SOURCE_COMMIT",
                      "IMMUTABLE_PRE_HOLDOUT_HYPOTHESIS_NOT_EDITED_AFTER_FIRST_VERIFIED_RUN",
                      "TRADING_DAY_AND_PIT_UNIVERSE_SOURCE_ATTESTATION",
                      "HOLDOUT_STRATEGY_VALIDATION_ON_UNTOUCHED_DATA"
                    ])
    except (ValueError,TypeError,OverflowError):
        return reject("INVALID_FREEZE_DATETIME_OR_BOUNDARIES")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-commit",required=True)
    p.add_argument("--fold-report",required=True)
    p.add_argument("--hypothesis",default="MA20_CROSS_UPWARD_COMPLETED_DAILY_BAR_RESEARCH_ONLY")
    p.add_argument("--validation-start",required=True)
    p.add_argument("--validation-end",required=True)
    p.add_argument("--evidence-created-utc",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    fold=json.loads(Path(a.fold_report).read_text())
    if (fold.get("phase")!="P2_ARCHIVED_CHRONOLOGY_ALL_PAGES_ACCOUNTING" or
        fold.get("status")!="ALL_SOURCE_PAGES_ACCOUNTED_NOT_OOS_CERTIFICATION" or
        fold.get("trade_gate")!="BLOCKED" or
        fold.get("orders")!=[] or fold.get("historical_OOS_validated") is not False or
        fold.get("all_pages_accounted") is not True):
        raise SystemExit("unsafe P2 fold evidence")
    result=register(source_commit=a.source_commit,hypothesis=a.hypothesis,
        validation_start=a.validation_start,validation_end=a.validation_end,
        evidence_created_at_utc=a.evidence_created_utc,
        fold_source_sha256=fold["fold_configuration_sha256"])
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result.get(k) for k in (
        "status","parameter_candidate_sha256","historical_OOS_validated",
        "parameters_frozen_before_historical_holdout_verified","trade_gate")}))
    if result["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
