"""Bounded read-only recovery of old successful main-branch P2 research artifacts.

Only native GitHub Actions artifacts from completed successful *main* runs
of the exact P2 workflow qualify. Every imported old page must independently
pass the original-CSV SHA replay and cross-run coverage auditor. Missing,
expired, PR, mismatched, corrupt or pre-pagination artifacts are skipped;
no success state is synthesized. No brokerage calls or trading.
"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from collector.p2_feature_coverage_ledger import summarize

WORKFLOW="p2-real-archive-feature-observation.yml"
ARTIFACT_PREFIX="p2-real-archive-feature-observation-"
SHA64=re.compile(r"[0-9a-f]{64}\Z")
MAX_PROBES=8
MAX_IMPORTS=4

def eligible(run,current_run_id):
    if not isinstance(run,dict):return False
    rid=run.get("databaseId")
    return (
        type(rid) is int and rid>0 and rid!=current_run_id
        and run.get("conclusion")=="success"
        and run.get("status")=="completed"
        and run.get("headBranch")=="main"
        and run.get("event") in ("push","workflow_run","workflow_dispatch","schedule")
    )

def import_report(report,run_id,epoch,ledger,archive_epoch,prior_reports):
    """Validate downloaded report against current immutable source, not run label."""
    if not isinstance(report,dict) or not isinstance(epoch,str) or not SHA64.fullmatch(epoch):
        return False,"INVALID_REPORT_OR_EPOCH"
    if report.get("source_epoch_sha256")!=epoch:
        return False,"DIFFERENT_FROZEN_EPOCH"
    if report.get("phase")!="P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY":
        return False,"LEGACY_ARTIFACT_NOT_PAGED"
    if report.get("trade_gate")!="BLOCKED" or report.get("orders")!=[]:
        return False,"UNSAFE_TRADE_FIELDS"
    try:
        tested=summarize(archive_epoch,ledger,prior_reports+[report])
    except (ValueError,KeyError,TypeError,OSError):
        return False,"UNREADABLE_EVIDENCE"
    if tested.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED":
        return False,"ORIGINAL_RECEIPT_REPLAY_REJECTED"
    return True,"INDEPENDENT_ORIGINALS_REPLAY_VALIDATED"

def gh(args,timeout=45):
    cmd=["gh",*args]
    return subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,check=False)

def recover(repo,epoch,archive_epoch,ledger,folder,current_run_id):
    if (not isinstance(repo,str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+",repo)
        or not isinstance(epoch,str) or not SHA64.fullmatch(epoch)
        or type(current_run_id) is not int or current_run_id<1):
        raise ValueError("unsafe GitHub backfill arguments")
    dest=Path(folder)
    dest.mkdir(parents=True,exist_ok=True)
    stored=[]
    for path in sorted(dest.glob("*.json")):
        if not path.stem.isdecimal():raise ValueError("unknown stored run receipt")
        stored.append(json.loads(path.read_text()))
    # Existing data must pass a fresh full original-byte replay.
    previous=summarize(archive_epoch,ledger,stored)
    if previous.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED":
        raise ValueError("existing persistent P2 coverage failed re-audit")
    result=gh(["run","list","--repo",repo,"--workflow",WORKFLOW,
               "--json","databaseId,conclusion,status,headBranch,event",
               "--limit","80"])
    if result.returncode:
        raise ValueError("cannot authenticate prior GitHub workflow list")
    runs=json.loads(result.stdout)
    if not isinstance(runs,list):raise ValueError("unexpected GitHub workflow list")
    inspected=0;imported=[];skipped=[]
    for run in runs:
        if inspected>=MAX_PROBES or len(imported)>=MAX_IMPORTS:
            break
        if not eligible(run,current_run_id):continue
        rid=run["databaseId"]
        target=dest/(str(rid)+".json")
        if target.exists():continue
        inspected+=1
        with tempfile.TemporaryDirectory() as tmp:
            download=gh(["run","download",str(rid),"--repo",repo,
                         "-n",ARTIFACT_PREFIX+str(rid),"-D",tmp],timeout=75)
            if download.returncode:
                skipped.append({"run":rid,"reason":"ARTIFACT_UNAVAILABLE_OR_EXPIRED"})
                continue
            file=Path(tmp)/"p2_real_archive_feature_observation.json"
            if not file.is_file() or file.stat().st_size>2_000_000:
                skipped.append({"run":rid,"reason":"MISSING_OR_OVERSIZE_RESEARCH_REPORT"})
                continue
            try:report=json.loads(file.read_text())
            except (UnicodeError,ValueError):
                skipped.append({"run":rid,"reason":"INVALID_RESEARCH_JSON"})
                continue
            allowed,reason=import_report(
                report,rid,epoch,ledger,archive_epoch,stored)
            if not allowed:
                skipped.append({"run":rid,"reason":reason})
                continue
            # Store only original report bytes; no rewriting source provenance.
            target.write_bytes(file.read_bytes())
            stored.append(report)
            imported.append(rid)
    final=summarize(archive_epoch,ledger,stored)
    if final.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED":
        raise ValueError("backfilled research receipts fail combined replay")
    return {"phase":"P2_HISTORICAL_RESEARCH_ARTIFACT_BACKFILL",
            "status":"REPLAYED_OLD_MAIN_ARTIFACTS_ONLY",
            "source_epoch_sha256":epoch,
            "inspected_runs":inspected,
            "imported_run_ids":imported,
            "skipped_runs":skipped,
            "observed_archived_shards_after_import":final["observed_archived_shards"],
            "full_market_universe_verified":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--source-epoch",required=True)
    p.add_argument("--archive-epoch",required=True)
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--receipts",required=True)
    p.add_argument("--run-id",required=True,type=int)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    ledger=json.loads(Path(a.checkpoint).read_text())
    result=recover(a.repo,a.source_epoch,a.archive_epoch,ledger,
                   a.receipts,a.run_id)
    target=Path(a.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
        "status","inspected_runs","imported_run_ids",
        "observed_archived_shards_after_import","trade_gate")}))
if __name__=="__main__":main()
