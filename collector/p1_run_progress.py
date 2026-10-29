"""Read-only per-run P1 progress acceptance: green CI != newly archived data.

A report distinguishes newly observed immutable same-epoch shards from mere
successful pipeline execution. Never combines roster epochs or opens trading.
"""
import argparse
import json
import os
from pathlib import Path
from collector.p1_checkpoint import validate as validate_checkpoint


def assess(plan, ledger, archive, selection, policy, prior=None):
    current=validate_checkpoint(ledger)
    if (plan.get("source_sha256")!=current["source_sha256"]
            or plan.get("shard_count")!=current["shard_count"]
            or plan.get("trade_gate")!="BLOCKED"):
        raise ValueError("progress plan belongs to different frozen roster")
    if (archive.get("source_sha256")!=current["source_sha256"]
            or archive.get("trade_gate")!="BLOCKED"
            or archive.get("historical_PIT_verified") is not False
            or archive.get("ledger_issuers")!=current["completed_issuers"]):
        raise ValueError("archive audit does not match same-epoch ledger")
    if (type(archive.get("archived_issuers")) is not int
            or type(archive.get("archive_gap_issuers")) is not int
            or archive["archived_issuers"]<0
            or archive["archived_issuers"]>current["completed_issuers"]
            or archive["archive_gap_issuers"]!=current["completed_issuers"]-archive["archived_issuers"]):
        raise ValueError("invalid archival coverage counters")
    if prior is not None:
        previous=validate_checkpoint(prior)
        if (previous["source_sha256"]!=current["source_sha256"]
                or previous["shard_count"]!=current["shard_count"]):
            raise ValueError("cross-epoch progress is forbidden")
        old={x["index"]:x for x in previous["completed"]}
    else:
        old={}
    new={x["index"]:x for x in current["completed"]}
    if any(index not in new or new[index]!=item for index,item in old.items()):
        raise ValueError("durable progress regression or replaced receipt")
    indices=selection.get("selected_shards")
    if (not isinstance(indices,list) or not 1<=len(indices)<=2
            or any(type(i) is not int or not 0<=i<current["shard_count"] for i in indices)
            or len(set(indices))!=len(indices)
            or selection.get("selected_count")!=len(indices)
            or selection.get("trade_gate")!="BLOCKED"):
        raise ValueError("invalid selected research shards")
    actual=sorted(set(new)-set(old))
    if not set(actual).issubset(indices):
        raise ValueError("new shard was not selected in this run")
    effective=policy.get("effective_shard_count")
    if (type(effective) is not int or effective not in (1,2)
            or len(actual)>effective
            or policy.get("trade_gate")!="BLOCKED"
            or policy.get("historical_PIT_verified") is not False
            or policy.get("orders")!=[]
            or policy.get("executable_candidates")!=[]
            or policy.get("accepted_second") is not (effective==2)
            or (effective==2 and len(indices)!=2)):
        raise ValueError("invalid effective shard acceptance")
    full_archive=archive["archive_gap_issuers"]==0
    state=("DURABLE_PROGRESS" if actual and full_archive else
           "ARCHIVE_GAP" if not full_archive else "SUCCESS_NO_NEW_SHARD")
    return {
        "phase":"P1_READ_ONLY_RUN_PROGRESS",
        "source_sha256":current["source_sha256"],
        "status":state,
        "previous_shards":len(old),
        "current_shards":len(new),
        "new_selected_shards":actual,
        "new_shard_count":len(actual),
        "selected_count":len(indices),
        "effective_shard_count":effective,
        "archived_issuers":archive["archived_issuers"],
        "archive_gap_issuers":archive["archive_gap_issuers"],
        "new_shards_durably_accepted":len(actual) if full_archive else 0,
        "trade_gate":"BLOCKED",
        "historical_PIT_verified":False,
        "orders":[],
        "executable_candidates":[],
    }


def main():
    parser=argparse.ArgumentParser()
    for name in ("plan","ledger","archive","selection","policy","out"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--prior")
    parser.add_argument("--summary-file",default=os.environ.get("GITHUB_STEP_SUMMARY"))
    args=parser.parse_args()
    read=lambda path:json.loads(Path(path).read_text())
    report=assess(
        read(args.plan),read(args.ledger),read(args.archive),
        read(args.selection),read(args.policy),
        read(args.prior) if args.prior and Path(args.prior).is_file() else None,
    )
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    if args.summary_file:
        with Path(args.summary_file).open("a") as summary:
            summary.write(
                "\n### P1 actual durable research progress\n"
                f"- Frozen roster SHA: `{report['source_sha256']}`\n"
                f"- New ledger shards: **{report['new_shard_count']}**\n"
                f"- Newly accepted with full archive audit: **{report['new_shards_durably_accepted']}**\n"
                f"- Current completed: **{report['current_shards']}**\n"
                f"- Archive gap: **{report['archive_gap_issuers']} issuers**\n"
                f"- Result: **{report['status']}**; trading BLOCKED.\n"
            )
    print(json.dumps(report))


if __name__=="__main__":
    main()
