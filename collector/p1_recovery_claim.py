"""Create-only dry-run slot marker in an existing independent Git branch.

This is an auditable observation deduplication key, NOT a collection dispatch.
A future dispatcher must have separately reviewed idempotency and permission.
"""
import argparse,datetime as dt,hashlib,json,os,re
from pathlib import Path
from collector.intraday_snapshot_archive import api,BRANCH,REPO_RE

PHASE="P1_MISSED_SLOT_RECOVERY_DRY_RUN_CLAIM"
PATH_RE=re.compile(r"^recovery-claims/20\d{2}-\d{2}-\d{2}/[0-2]\d[0-5]\d\.json$")
def claim_path(report):
    if not isinstance(report,dict) or report.get("state")!="ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW":
        return None
    if (report.get("auto_dispatch_enabled") is not False or
            report.get("auto_dispatched") is not False or
            report.get("trade_gate")!="BLOCKED" or
            report.get("requested_shards")!=1 or
            report.get("orders")!=[] or report.get("executable_candidates")!=[]):
        raise ValueError("dry-run claim preconditions invalid")
    stamp=dt.datetime.fromisoformat(report["slot"])
    if stamp.tzinfo is None or stamp.utcoffset()!=dt.timedelta(hours=8):
        raise ValueError("claim slot must be Beijing local")
    # Schedule slots only, never arbitrary times; hour must match actual cron.
    if stamp.second or stamp.microsecond or stamp.minute!=10:
        raise ValueError("claim does not match historical scheduled slot")
    hours=(1,8,9,11,13,15,17,19,21,23) if stamp.weekday()<5 else (9,15,19,23)
    if stamp.hour not in hours:raise ValueError("claim outside approved schedule")
    path=f"recovery-claims/{stamp.date().isoformat()}/{stamp:%H%M}.json"
    if not PATH_RE.fullmatch(path):raise ValueError("invalid recovery claim path")
    return path

def reserve(repo,report,run_id):
    path=claim_path(report)
    if path is None:
        return {"phase":PHASE,"state":"NOT_ELIGIBLE","claim_path":None,
                "auto_dispatched":False,"trade_gate":"BLOCKED"}
    if not isinstance(repo,str) or not REPO_RE.fullmatch(repo):
        raise ValueError("invalid repository")
    if type(run_id) is not int or run_id<1:raise ValueError("invalid run id")
    # Claim lives in the already existing research branch. It never mutates main
    # or the immutable historical CSV data/archive, only this slot marker.
    endpoint=f"contents/{path}?ref={BRANCH}"
    existing=api(repo,endpoint)
    if existing is not None:
        if not isinstance(existing,dict) or existing.get("path")!=path:
            raise ValueError("existing marker not readable")
        return {"phase":PHASE,"state":"ALREADY_CLAIMED","claim_path":path,
                "auto_dispatched":False,"trade_gate":"BLOCKED"}
    record={
        "phase":PHASE,"slot":report["slot"],"origin_check_run_id":run_id,
        "mode":"DRY_RUN_NO_DISPATCH","single_shard_upper_bound":1,
        "historical_collection_executed":False,"auto_dispatched":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]
    }
    raw=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
    try:
        # Create-only: DO NOT set an existing blob SHA to overwrite a marker.
        api(repo,f"contents/{path}",method="PUT",data={
            "message":"audit(p1): claim missing historical slot DRY RUN [NO TRADES]",
            "branch":BRANCH,"content":__import__("base64").b64encode(raw).decode()})
    except RuntimeError:
        # A competing Actions job might have won the immutable-path race.
        competitor=api(repo,endpoint)
        if not isinstance(competitor,dict) or competitor.get("path")!=path:
            raise
        return {"phase":PHASE,"state":"ALREADY_CLAIMED","claim_path":path,
                "auto_dispatched":False,"trade_gate":"BLOCKED"}
    saved=api(repo,endpoint)
    if not isinstance(saved,dict) or saved.get("path")!=path:
        raise ValueError("claim readback missing")
    if __import__("base64").b64decode(saved.get("content",""))!=raw:
        raise ValueError("claim readback differs")
    return {"phase":PHASE,"state":"DRY_RUN_CLAIMED","claim_path":path,
            "sha256":hashlib.sha256(raw).hexdigest(),
            "auto_dispatched":False,"trade_gate":"BLOCKED"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--eligibility",required=True)
    p.add_argument("--repo",default=os.getenv("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=json.loads(Path(args.eligibility).read_text())
    if report.get("phase")!="P1_MISSED_SLOT_RECOVERY_READ_ONLY_GUARD":
        raise ValueError("wrong eligibility phase")
    result=reserve(args.repo,report,int(os.environ["GITHUB_RUN_ID"]))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
