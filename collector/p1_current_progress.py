"""Read-only, source-pinned P1 durable coverage report; never a trading signal."""
import argparse
import base64
import json
import re
import subprocess
from pathlib import Path

from collector.p1_checkpoint import validate, epoch_path
from collector.p1_roster_lock import unpack

REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")

def report(lock, ledger):
    unpack(lock)  # Recheck original CSV SHA and canonical vendor roster receipt.
    validate(ledger)
    if lock["source_sha256"] != ledger["source_sha256"]:
        raise ValueError("mixed P1 source roster epochs")
    if ledger["shard_count"] != (lock["original_quality"]["mainboard_prefix_rows"]+7)//8:
        raise ValueError("P1 shard count not consistent with pinned source roster")
    if (ledger["completed_issuers"] > lock["original_quality"]["mainboard_prefix_rows"] or
            ledger["completed_issuers"] > 8 * ledger["completed_shards"]):
        raise ValueError("overcounted source issuers")
    done=ledger["completed_shards"]
    total=ledger["shard_count"]
    return {
        "phase":"P1_DURABLE_PINNED_PROGRESS",
        "status":"VERIFIED_DURABLE_LEDGER_NOT_MARKET_CERTIFICATION",
        "source_sha256":lock["source_sha256"],
        "roster_requested_day_not_publication":lock["source_requested_day"],
        "roster_origin_run_id":lock["created_run_id"],
        "completed_shards":done,
        "total_shards":total,
        "pending_shards":total-done,
        "completed_issuers":ledger["completed_issuers"],
        "total_issuers":lock["original_quality"]["mainboard_prefix_rows"],
        "pending_issuers":lock["original_quality"]["mainboard_prefix_rows"]-ledger["completed_issuers"],
        "research_coverage_percent":round(100*done/total,4),
        "historical_PIT_verified":False,
        "full_market_bars_certified":False,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
    }

def remote_json(repo,path):
    if not isinstance(repo,str) or not REPO.fullmatch(repo):
        raise ValueError("invalid GitHub repository")
    call=subprocess.run(
        ["gh","api",f"repos/{repo}/contents/{path}","--method","GET","-f","ref=main"],
        capture_output=True,text=True,check=True,timeout=35)
    response=json.loads(call.stdout)
    return json.loads(base64.b64decode(response["content"],validate=True).decode("utf-8"))

def capture(repo):
    lock=remote_json(repo,"evidence/p1_active_roster.json")
    digest=lock.get("source_sha256")
    path=epoch_path(digest)
    ledger=remote_json(repo,path)
    return report(lock,ledger)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:
        result=capture(args.repo)
    except (ValueError,KeyError,TypeError,UnicodeError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired,OSError) as exc:
        result={
          "phase":"P1_DURABLE_PINNED_PROGRESS",
          "status":"CHECKPOINT_UNAVAILABLE_OR_UNVERIFIED",
          "reason_category":type(exc).__name__,
          "completed_shards":None,"total_shards":None,
          "research_coverage_percent":None,
          "historical_PIT_verified":False,"trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],
        }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
    if result["status"]!="VERIFIED_DURABLE_LEDGER_NOT_MARKET_CERTIFICATION":
        raise SystemExit("P1 live checkpoint cannot be certified; no stale count substituted")

if __name__=="__main__":
    main()
