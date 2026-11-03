"""At-most-once dispatch request for bounded P1 research shard recovery.

A create-only attempt marker is committed BEFORE contacting workflow_dispatch.
Any uncertain API outcome is never retried automatically for the same slot.
A 204 response only proves GitHub accepted the request, not that collection ran.
"""
import argparse,base64,datetime as dt,json,os,re,subprocess
from pathlib import Path
from collector.intraday_snapshot_archive import api,BRANCH,REPO_RE
from collector.p1_safe_recovery import eligibility,workflow_runs,TZ
from collector.p1_recovery_claim import claim_path
from collector.p1_recovery_origin_token import token_for_attempt

TARGET="p1-fresh-vendor-roster.yml"
ATTEMPT_PHASE="P1_SINGLE_SHARD_DISPATCH_ATTEMPT"
def prepare(repo,preflight,now,runs,total_count,runner_id):
    if not isinstance(preflight,dict) or preflight.get("state")!="PREFLIGHT_PASS_DISPATCH_NOT_ENABLED":
        return None,"PREFLIGHT_NOT_PASSED"
    if (preflight.get("dispatch_authorized") is not False or
            preflight.get("dispatch_attempted") is not False or
            preflight.get("historical_collection_executed") is not False or
            preflight.get("trade_gate")!="BLOCKED" or
            preflight.get("requested_shards_if_enabled")!=1):
        return None,"PREFLIGHT_FIELDS_INVALID"
    if not isinstance(repo,str) or not REPO_RE.fullmatch(repo):
        return None,"REPO_INVALID"
    if type(runner_id) is not int or runner_id<1:
        return None,"RUNNER_ID_INVALID"
    latest=eligibility(now,runs,total_count=total_count)
    if (latest.get("state")!="ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW" or
            latest.get("slot")!=preflight.get("slot")):
        return None,"LATEST_SAFETY_RECHECK_BLOCKED"
    claim_input=dict(state=latest["state"],slot=latest["slot"],
          requested_shards=1,auto_dispatch_enabled=False,auto_dispatched=False,
          trade_gate="BLOCKED",orders=[],executable_candidates=[])
    slot_claim=claim_path(claim_input)
    if preflight.get("claim_path")!=slot_claim:
        return None,"CLAIM_MISMATCH"
    # Keep execution attempts separate from existing DRY_RUN research claims.
    attempt_path=slot_claim.replace("recovery-claims/","recovery-dispatch-attempts/")
    return {
        "phase":ATTEMPT_PHASE,"slot":latest["slot"],
        "origin_check_run_id":runner_id,"dry_run_claim_path":slot_claim,
        "attempt_path":attempt_path,"requested_shards":1,
        "state":"DISPATCH_ATTEMPT_RESERVED",
        "workflow":TARGET,"ref":"main",
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    },None

def reserve_attempt(repo,record):
    path=record["attempt_path"]
    old=api(repo,f"contents/{path}?ref={BRANCH}")
    if old is not None:
        if not isinstance(old,dict) or old.get("path")!=path:
            raise ValueError("attempt ownership ambiguous")
        return False
    raw=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
    try:
        api(repo,f"contents/{path}",method="PUT",data={
            "message":"audit(p1): reserve one research dispatch attempt [NO TRADES]",
            "branch":BRANCH,
            "content":base64.b64encode(raw).decode(),
        })
    except RuntimeError:
        # A concurrent job may have won; no second request is allowed.
        winner=api(repo,f"contents/{path}?ref={BRANCH}")
        if not isinstance(winner,dict) or winner.get("path")!=path:
            raise
        return False
    saved=api(repo,f"contents/{path}?ref={BRANCH}")
    if not isinstance(saved,dict) or saved.get("path")!=path or (
            base64.b64decode(saved.get("content",""))!=raw):
        raise ValueError("dispatch attempt receipt readback mismatch")
    return True

def request_once(repo,record,*,enabled=False):
    if enabled is not True:
        return "DISPATCH_DISABLED"
    if record is None:
        return "DISPATCH_BLOCKED"
    if not reserve_attempt(repo,record):
        return "ALREADY_RESERVED_NO_RETRY"
    # Non-idempotent network request: no retries, regardless of failure reason.
    # A request accepted by GitHub does not mean its workflow completed.
    token=token_for_attempt(record)
    payload=json.dumps({"ref":"main","inputs":{"shards_per_run":"1","recovery_token":token}})
    call=subprocess.run(
        ["gh","api",f"repos/{repo}/actions/workflows/{TARGET}/dispatches",
         "--method","POST","--input","-"],input=payload,text=True,
        capture_output=True,timeout=30,check=False)
    if call.returncode!=0:
        return "DISPATCH_OUTCOME_UNKNOWN_DO_NOT_RETRY"
    return "DISPATCH_REQUEST_ACCEPTED_NOT_COLLECTION_VERIFIED"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--preflight",required=True)
    p.add_argument("--repo",default=os.getenv("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    args=p.parse_args()
    now=dt.datetime.now(TZ)
    # Disabled unless the workflow explicitly opts in; never use a user input
    # or untrusted file as authority to enable a dispatch.
    enabled=os.getenv("P1_RECOVERY_EXECUTION_ENABLED","false")=="true"
    report={"phase":ATTEMPT_PHASE,"trade_gate":"BLOCKED","orders":[],
            "executable_candidates":[],"historical_collection_verified":False,
            "auto_dispatch_enabled":enabled,"request_status":"DISPATCH_BLOCKED"}
    try:
        preflight=json.loads(Path(args.preflight).read_text())
        runs,total=workflow_runs(args.repo)
        record,reason=prepare(args.repo,preflight,now,runs,total,
                              int(os.environ["GITHUB_RUN_ID"]))
        report["guard_reason"]=reason
        report["slot"]=preflight.get("slot")
        report["request_status"]=request_once(args.repo,record,enabled=enabled)
        if record is not None:report["attempt_path"]=record["attempt_path"]
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired,
            subprocess.CalledProcessError,RuntimeError):
        report["request_status"]="GUARD_OR_API_UNAVAILABLE_NO_AUTOMATIC_RETRY"
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    if report["request_status"].endswith("DO_NOT_RETRY"):
        print("::warning::Research dispatch request outcome unknown. No retry permitted for this slot.")
if __name__=="__main__":main()
