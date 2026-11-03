"""Independent, fail-closed dispatch-preflight evidence for P1 recovery.

NO dispatch is performed here. Dry-run slot claims are NOT execution receipts.
A later explicitly reviewed executor must reserve a distinct immutable dispatch
attempt before contacting workflow_dispatch and must record any unknown outcome
as attempted, not retry blindly.
"""
import argparse,datetime as dt,json,os,re,subprocess
from pathlib import Path
from collector.intraday_snapshot_archive import api,BRANCH,REPO_RE
from collector.p1_recovery_claim import claim_path
from collector.p1_safe_recovery import eligibility,workflow_runs,TZ

PHASE="P1_RECOVERY_DISPATCH_PREFLIGHT"
RECORD_PHASE="P1_MISSED_SLOT_RECOVERY_DRY_RUN_CLAIM"

def inspect(repo,claim_report,now,runs,total_count):
    if not isinstance(repo,str) or not REPO_RE.fullmatch(repo):
        raise ValueError("invalid repository")
    base={"phase":PHASE,"mode":"DISPATCH_DISABLED_RESEARCH_GUARD",
          "dispatch_authorized":False,"dispatch_attempted":False,
          "historical_collection_executed":False,
          "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    if not isinstance(claim_report,dict) or claim_report.get("state")!="DRY_RUN_CLAIMED":
        return dict(base,state="BLOCKED",reason="NO_NEW_DRY_RUN_CLAIM")
    path=claim_report.get("claim_path")
    if not isinstance(path,str) or not re.fullmatch(
            r"recovery-claims/20\d\d-\d\d-\d\d/\d{4}\.json",path):
        return dict(base,state="BLOCKED",reason="INVALID_CLAIM_PATH")
    remote=api(repo,f"contents/{path}?ref={BRANCH}")
    if not isinstance(remote,dict) or remote.get("path")!=path:
        return dict(base,state="BLOCKED",reason="CLAIM_NOT_VERIFIED_REMOTELY")
    import base64
    try:
        claim=json.loads(base64.b64decode(remote["content"]))
    except (KeyError,ValueError,TypeError):
        return dict(base,state="BLOCKED",reason="INVALID_REMOTE_CLAIM")
    if (claim.get("phase")!=RECORD_PHASE or
            claim.get("mode")!="DRY_RUN_NO_DISPATCH" or
            claim.get("auto_dispatched") is not False or
            claim.get("historical_collection_executed") is not False or
            claim.get("trade_gate")!="BLOCKED" or
            claim.get("orders")!=[] or claim.get("executable_candidates")!=[] or
            claim.get("origin_check_run_id")!=int(os.environ.get("GITHUB_RUN_ID","0"))):
        return dict(base,state="BLOCKED",reason="CLAIM_PROVENANCE_MISMATCH")
    source={"state":"ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW",
            "slot":claim.get("slot"),"requested_shards":1,
            "auto_dispatch_enabled":False,"auto_dispatched":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    try:
        if claim_path(source)!=path:
            return dict(base,state="BLOCKED",reason="CLAIM_SLOT_PATH_MISMATCH")
    except (TypeError,ValueError,KeyError):
        return dict(base,state="BLOCKED",reason="INVALID_CLAIM_SLOT")
    reevaluated=eligibility(now,runs,total_count=total_count)
    if (reevaluated.get("state")!="ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW" or
            reevaluated.get("slot")!=source["slot"]):
        return dict(base,state="BLOCKED",reason="FRESH_P1_GUARD_BLOCKED",
                    fresh_guard_reason=reevaluated.get("reason"))
    # A *separate*, create-only execution claim would be required; this marker
    # is dry-run only, so the only permitted outcome remains NOT DISPATCHED.
    return dict(base,state="PREFLIGHT_PASS_DISPATCH_NOT_ENABLED",
                reason="AWAITING_ATOMIC_EXECUTION_ATTEMPT_RECEIPT",
                claim_path=path,slot=source["slot"],requested_shards_if_enabled=1)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--claim",required=True)
    p.add_argument("--repo",default=os.getenv("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    args=p.parse_args()
    now=dt.datetime.now(TZ)
    try:
        claim=json.loads(Path(args.claim).read_text())
        runs,total=workflow_runs(args.repo)
        result=inspect(args.repo,claim,now,runs,total)
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        result={"phase":PHASE,"state":"BLOCKED","reason":"PREFLIGHT_INPUT_UNAVAILABLE",
                "mode":"DISPATCH_DISABLED_RESEARCH_GUARD",
                "dispatch_authorized":False,"dispatch_attempted":False,
                "historical_collection_executed":False,"trade_gate":"BLOCKED",
                "orders":[],"executable_candidates":[]}
    dst=Path(args.out);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
