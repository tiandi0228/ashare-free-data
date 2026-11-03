"""Unified read-only multi-lane progress and explicit blocking matrix.

No independent evidence can open the gate merely by marking itself certified.
Historical vendor shards measure ingestion only; they do not measure the full
project development percentage or serve as point-in-time trading certification.
"""
import argparse,json
from pathlib import Path
from collector.p1_checkpoint import validate

PHASE="PARALLEL_RESEARCH_READINESS_MATRIX"
LANES={
    "ranking":"MAINBOARD_UNIVERSE_RESEARCH_RANKING",
    "quotes":"TWO_SOURCE_QUOTE_TIME_ALIGNMENT",
    "pit":"PIT_STATUS_AND_DISCLOSURE_COVERAGE",
    "forward":"FORWARD_SIMULATION_AND_REVIEW_CONTRACT",
}
def summarize(checkpoint,reports):
    base={"phase":PHASE,"trade_gate":"BLOCKED","orders":[],
          "executable_candidates":[],"buy_recommendations_authorized":False,
          "production_ready":False,"overall_project_percentage":None}
    if checkpoint is None:
        history={"status":"CHECKPOINT_UNAVAILABLE","completed_shards":None,
                 "total_shards":None,"completed_issuers":None,
                 "ingestion_percentage":None}
    else:
        try:
            validate(checkpoint)
            total=checkpoint["shard_count"]
            done=checkpoint["completed_shards"]
            history={"status":"INGESTION_INCOMPLETE" if done<total else "INGESTION_SHARDS_COMPLETE_NOT_CERTIFIED",
                     "completed_shards":done,"total_shards":total,
                     "completed_issuers":checkpoint["completed_issuers"],
                     "ingestion_percentage":round(100*done/total,2),
                     "source_sha256":checkpoint["source_sha256"]}
        except (ValueError,KeyError,TypeError,AttributeError,ZeroDivisionError):
            history={"status":"CHECKPOINT_INVALID","completed_shards":None,
                     "total_shards":None,"completed_issuers":None,
                     "ingestion_percentage":None}
    matrix={}
    for key,expected in LANES.items():
        report=reports.get(key) if isinstance(reports,dict) else None
        if not isinstance(report,dict) or report.get("phase")!="PARALLEL_FOUR_LANE_RESEARCH_CONTRACT" or (
            report.get("lane")!=expected or report.get("trade_gate")!="BLOCKED"
            or report.get("certified") is not False or report.get("orders")!=[]
            or report.get("executable_candidates")!=[] or report.get("actionable_buy_signals")!=[]):
            matrix[key]={"status":"EVIDENCE_MISSING_OR_INVALID","code_test_proven":False,
                         "production_certified":False}
        else:
            matrix[key]={"status":report.get("status"),"code_test_proven":False,
                         "structural_evidence_received":True,
                         "production_certified":False,
                         "reasons":report.get("reasons",[])}
    return dict(base,history=history,lanes=matrix,
                unresolved=[
                  "HISTORICAL_DATA_INGESTION_AND_INDEPENDENT_REPLAY",
                  "OFFICIAL_HISTORICAL_POINT_IN_TIME_MEMBERSHIP",
                  "FULL_MAINBOARD_UNIVERSE_AND_OUT_OF_SAMPLE_STRATEGY",
                  "INDEPENDENT_REALTIME_QUOTES_AND_COMPLETE_ONE_MINUTE_BARS",
                  "BROKER_FILLS_FEES_T_PLUS_ONE_AND_FORWARD_VALIDATION",
                ],
                interpretation="Only historical shard ingestion has a quantitative completion denominator; pass/fail source reports are not a full project percentage")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkpoint")
    for key in LANES:p.add_argument("--"+key)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    def read(path):
        try:return json.loads(Path(path).read_text()) if path else None
        except (OSError,ValueError,UnicodeError):return None
    result=summarize(read(args.checkpoint),
                     {key:read(getattr(args,key)) for key in LANES})
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"history":result["history"]["status"],
                      "trade_gate":"BLOCKED","production_ready":False}))
if __name__=="__main__":main()
