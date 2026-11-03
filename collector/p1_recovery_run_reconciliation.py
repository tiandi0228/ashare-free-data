"""Read-only reconciliation of P1 research recovery dispatch attempts.

A run appearing near a dispatch attempt is not proof of causal linkage.
Never label historical data completed without the original run's verified
archive/ledger receipt and a matching pre/post checkpoint baseline.
"""
import argparse,base64,datetime as dt,json,os,re,subprocess
from pathlib import Path
from collector.intraday_snapshot_archive import api,BRANCH,REPO_RE
from collector.p1_safe_recovery import workflow_runs,iso,TZ

PHASE="P1_RECOVERY_RUN_RECONCILIATION"
ATTEMPT_RE=re.compile(r"recovery-dispatch-attempts/20\d\d-\d\d-\d\d/\d{4}\.json\Z")
def reconcile(attempt,runs,now,*,original_run=None):
    base={"phase":PHASE,"trade_gate":"BLOCKED","orders":[],
          "executable_candidates":[],"historical_collection_verified":False,
          "verified_new_shards":0,"causal_dispatch_link_verified":False}
    if not isinstance(attempt,dict) or attempt.get("phase")!="P1_SINGLE_SHARD_DISPATCH_ATTEMPT":
        return dict(base,state="NO_VALID_DISPATCH_ATTEMPT",candidate_runs=[])
    if attempt.get("state")!="DISPATCH_ATTEMPT_RESERVED" or (
            attempt.get("requested_shards")!=1 or attempt.get("trade_gate")!="BLOCKED"
            or attempt.get("orders")!=[] or attempt.get("executable_candidates")!=[]):
        return dict(base,state="INVALID_DISPATCH_ATTEMPT",candidate_runs=[])
    if not isinstance(runs,list):
        return dict(base,state="RUN_HISTORY_UNKNOWN",candidate_runs=[])
    if not isinstance(original_run,dict) or not isinstance(original_run.get("created_at"),str):
        return dict(base,state="ORIGIN_RUN_UNVERIFIED",candidate_runs=[])
    try:
        origin_time=iso(original_run["created_at"])
        slot=iso(attempt["slot"])
        if slot.utcoffset()!=dt.timedelta(hours=8):
            raise ValueError("not Beijing")
    except (KeyError,ValueError,TypeError,AttributeError):
        return dict(base,state="INVALID_TIME_PROVENANCE",candidate_runs=[])
    if original_run.get("id")!=attempt.get("origin_check_run_id"):
        return dict(base,state="ORIGIN_ID_MISMATCH",candidate_runs=[])
    candidates=[]
    for run in runs:
        if not isinstance(run,dict):continue
        if run.get("event")!="workflow_dispatch" or (
                run.get("path")!=".github/workflows/p1-fresh-vendor-roster.yml"):
            continue
        try:created=iso(run["created_at"])
        except (KeyError,ValueError,TypeError,AttributeError):continue
        # Requests cannot precede the checking runner. Bound to 15 minutes,
        # but NEVER interpret temporal proximity as proof of causation.
        if origin_time<=created<=origin_time+dt.timedelta(minutes=15):
            candidates.append({"run_id":run.get("id"),"created_at":run["created_at"],
                               "status":run.get("status"),
                               "conclusion":run.get("conclusion")})
    candidates.sort(key=lambda x:(str(x["created_at"]),str(x["run_id"])))
    if not candidates:state="NO_DISPATCH_RUN_OBSERVED"
    elif len(candidates)>1:state="MULTIPLE_RUNS_ATTRIBUTION_AMBIGUOUS"
    elif candidates[0]["status"]!="completed":state="CANDIDATE_RUN_PENDING"
    elif candidates[0]["conclusion"]!="success":state="CANDIDATE_RUN_NOT_SUCCESSFUL"
    else:state="CANDIDATE_RUN_SUCCESS_UNATTRIBUTED"
    return dict(base,state=state,candidate_runs=candidates,
                origin_check_run_id=attempt["origin_check_run_id"],
                slot=attempt["slot"],
                limitation="TIME_PROXIMITY_ONLY_NO_UNIQUE_DISPATCH_TOKEN_OR_ARCHIVE_RECEIPT")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result={"phase":PHASE,"state":"API_UNAVAILABLE","trade_gate":"BLOCKED",
            "historical_collection_verified":False,"verified_new_shards":0,
            "causal_dispatch_link_verified":False,"orders":[],"executable_candidates":[]}
    try:
        if not isinstance(a.repo,str) or not REPO_RE.fullmatch(a.repo):
            raise ValueError("invalid repo")
        # Only recent origin attempts: no past inferred missing-slot receipts.
        runs,total=workflow_runs(a.repo)
        # Read today's independent recovery-attempt directory, if present.
        today=dt.datetime.now(TZ).date().isoformat()
        listing=api(a.repo,f"contents/recovery-dispatch-attempts/{today}?ref={BRANCH}")
        if listing is None:
            result["state"]="NO_DISPATCH_ATTEMPTS"
        elif not isinstance(listing,list) or len(listing)>20:
            raise ValueError("invalid attempt directory")
        else:
            outcomes=[]
            for item in listing:
                path=item.get("path","")
                if not ATTEMPT_RE.fullmatch(path):raise ValueError("invalid attempt path")
                remote=api(a.repo,f"contents/{path}?ref={BRANCH}")
                attempt=json.loads(base64.b64decode(remote["content"]))
                origin=api(a.repo,f"actions/runs/{attempt['origin_check_run_id']}")
                item_result=reconcile(attempt,runs,dt.datetime.now(TZ),
                                      original_run=origin)
                item_result["attempt_path"]=path
                outcomes.append(item_result)
            result["state"]="READ_ONLY_RECONCILIATION"
            result["attempts"]=outcomes
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired):
        result["state"]="API_UNAVAILABLE"
    dst=Path(a.out);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"state":result["state"],
                      "attempts":[{"state":x["state"],"path":x["attempt_path"]}
                                  for x in result.get("attempts",[])],
                      "trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
