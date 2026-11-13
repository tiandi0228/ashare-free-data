"""Fail-closed P1 bounded gap preflight. Read-only; never grants archive writes."""
import argparse
import json
import re
from pathlib import Path
from collector.p1_checkpoint import validate as validate_ledger
from collector.p1_quad_pick import verify_frozen_plan

SHA64 = re.compile(r"[0-9a-f]{64}\Z")


def _receipts(ledger, total):
    validate_ledger(ledger)
    if ledger["shard_count"] != total:
        raise ValueError("wrong P1 shard denominator")
    return {r["index"]: (r["issuer_count"], r["manifest_sha256"], r["receipt_sha256"])
            for r in ledger["completed"]}


def check(plan, selected, initial_ledger, fresh_ledger, archive_status):
    """Require unchanged active source, checked ledgers and archive index equality.

    Caller must fetch fresh_ledger/archive_status just before vendor request,
    then perform another remote HEAD/SHA check immediately before ANY write.
    This function does not prove cross-repo atomicity or authorize writes.
    """
    verify_frozen_plan(plan)
    if (type(plan.get("shard_count")) is not int or
        not isinstance(plan.get("source_sha256"), str) or
        not SHA64.fullmatch(plan["source_sha256"])):
        raise ValueError("invalid source identity")
    source, total = plan["source_sha256"], plan["shard_count"]
    if (not isinstance(selected, list) or not 1 <= len(selected) <= 2 or
        any(type(i) is not int or not 0 <= i < total for i in selected) or
        len(selected) != len(set(selected))):
        raise ValueError("select 1-2 unique valid shards only")
    old = _receipts(initial_ledger,total)
    current = _receipts(fresh_ledger,total)
    if initial_ledger["source_sha256"] != source or fresh_ledger["source_sha256"] != source:
        raise ValueError("source epoch mismatch")
    if old != current:
        raise ValueError("checkpoint changed after selection")
    for i, (n, manifest, _) in current.items():
        shard = plan["shards"][i]
        if shard["count"] != n or shard["sha256"] != manifest:
            raise ValueError("original frozen manifest mismatch")
    if (not isinstance(archive_status, dict)
        or archive_status.get("source_sha256") != source
        or archive_status.get("trade_gate") != "BLOCKED"):
        raise ValueError("archive epoch or gate mismatch")
    archived = archive_status.get("archived_shards")
    if (not isinstance(archived, list) or
        any(type(i) is not int or i < 0 or i >= total for i in archived) or
        len(archived) != len(set(archived)) or
        set(archived) != set(current)):
        raise ValueError("archive/checkpoint index mismatch")
    if any(i in current for i in selected):
        raise ValueError("already archived shard selected")
    return {
        "phase":"P1_PREWRITE_GAP_GUARD",
        "status":"SAFE_FOR_BOUNDED_VENDOR_REQUEST_ONLY",
        "source_sha256":source,
        "selected_missing_shards":selected,
        "checkpoint_completed_shards":len(current),
        "total_shards":total,
        "archive_checkpoint_index_equality":True,
        "requires_second_remote_head_check_before_write":True,
        "permission_to_write_or_trade":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    for name in ("plan","selected","initial-checkpoint","fresh-checkpoint","archive-status","out"):
        p.add_argument("--"+name, type=Path, required=True)
    a=p.parse_args()
    load=lambda x:json.loads(x.read_text(encoding="utf-8"))
    selection=load(a.selected)
    if isinstance(selection,dict) and set(selection)=={"selected"}:
        selection=selection["selected"]
    result=check(load(a.plan),selection,load(a.initial_checkpoint),
                 load(a.fresh_checkpoint),load(a.archive_status))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__":
    main()
