"""Read-only P1 operational progress health, separate CI success from new shards.

Inputs are explicitly supplied GitHub Actions workflow run and the corresponding
run-scoped p1_run_progress.json. A successful job is not evidence of new data.
Never certify official PIT, complete market coverage, or trading.
"""
import argparse
import json
from pathlib import Path

WORKFLOW = "P1 fresh Baostock mainboard roster observation (NO TRADES)"


def assess(run, progress=None):
    if not isinstance(run, dict):
        raise ValueError("workflow run object required")
    rid=run.get("id")
    if type(rid) is not int or rid <= 0 or run.get("name") != WORKFLOW:
        raise ValueError("P1 workflow identity required")
    if run.get("head_branch") != "main" or run.get("event") not in ("schedule","workflow_dispatch","push"):
        raise ValueError("wrong branch or trigger")
    result = {
        "phase": "P1_OPERATIONAL_PROGRESS_SEPARATION",
        "run_id": rid,
        "run_conclusion": run.get("conclusion"),
        "workflow_success": run.get("status") == "completed" and run.get("conclusion") == "success",
        "run_bound_progress_verified": False,
        "actual_new_shards": None,
        "prior_shards": None,
        "current_shards": None,
        "progress_status": "UNVERIFIED_RUN_PROVENANCE",
        "historical_PIT_verified": False,
        "full_market_bars_certified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    if not result["workflow_success"]:
        return dict(result, progress_status="WORKFLOW_NOT_SUCCESSFUL")
    if progress is None:
        return result
    if not isinstance(progress, dict):
        raise ValueError("run progress object required")
    # Run provenance is an external envelope, not a field copied from old
    # artifact JSON. This makes accidental reuse from another run fail-closed.
    if type(progress.get("run_id")) is not int or progress["run_id"] != rid:
        raise ValueError("progress not bound to selected workflow run")
    p=progress.get("report")
    if (not isinstance(p, dict) or p.get("phase") != "P1_READ_ONLY_RUN_PROGRESS"
            or p.get("trade_gate") != "BLOCKED"
            or p.get("historical_PIT_verified") is not False
            or p.get("orders") != [] or p.get("executable_candidates") != []):
        raise ValueError("unsafe P1 run report")
    before=p.get("previous_shards")
    after=p.get("current_shards")
    new=p.get("new_shard_count")
    if (any(type(v) is not int for v in (before,after,new))
            or before<0 or after<before or new<0 or after-before!=new):
        raise ValueError("inconsistent P1 shard delta")
    result.update(run_bound_progress_verified=True,
                  actual_new_shards=new,prior_shards=before,current_shards=after,
                  progress_status="NEW_RESEARCH_SHARDS" if new else "SUCCESS_WITHOUT_NEW_SHARDS")
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",required=True,type=Path)
    ap.add_argument("--run-bound-progress",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    run=json.loads(a.run.read_text(encoding="utf-8"))
    prog=json.loads(a.run_bound_progress.read_text(encoding="utf-8")) if a.run_bound_progress else None
    output=assess(run,prog)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False))


if __name__=="__main__":
    main()
