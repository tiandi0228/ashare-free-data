"""Read-only LIVE GitHub P1 gap selection rehearsal: no provider, no archive writes."""
import argparse
import json
import os
import tempfile
from pathlib import Path

from collector.p1_fresh_shard_plan import plan as build_plan
from collector.p1_gap_remote_preflight import read_remote, verify
from collector.p1_roster_lock import unpack
from collector.p1_checkpoint import epoch_path, validate
from collector.p1_quad_pick import choose_gap_window


def rehearse(repo, fetch=read_remote):
    # Read original frozen vendor roster bytes from MAIN, not a PR fixture.
    lock = fetch(repo, "evidence/p1_active_roster.json", "main")
    original, receipt = unpack(lock)
    source = lock["source_sha256"]
    initial = fetch(repo, epoch_path(source), "main")
    validate(initial)
    if initial["source_sha256"] != source:
        raise ValueError("active roster and live checkpoint differ")
    with tempfile.TemporaryDirectory(prefix="p1_gap_rehearsal_") as folder:
        root = Path(folder)
        csv = root / "mainboard.csv"
        csv.write_bytes(original)
        frozen = build_plan(csv, root / "shards", receipt["requested_day"])
        if frozen["source_sha256"] != source:
            raise ValueError("rebuilt live roster plan source mismatch")
        pending = initial["pending_shards"]
        if not pending:
            selected = []
            raise ValueError("no missing P1 shards; manual backfill prohibited")
        chosen = choose_gap_window(frozen, initial, f"0:{frozen['shard_count']-1}", 2)
        selection = {
            "phase":"P1_BOUNDED_PILOT_SELECTION",
            "requested_shards":2,
            "selected_shards":chosen,
            "selected_count":len(chosen),
            "trade_gate":"BLOCKED","orders":[],
        }
        # Re-fetch current checkpoint and archive status independently.
        checked = verify(frozen, selection, initial, repo, fetch)
        # Even if the plan was valid at start, deny a source roster change now.
        lock_now = fetch(repo, "evidence/p1_active_roster.json", "main")
        unpack(lock_now)
        if lock_now["source_sha256"] != source:
            raise ValueError("source roster changed during read-only rehearsal")
        if checked["selected_missing_shards"] != chosen:
            raise ValueError("selected shard identity changed")
        return {
            "phase":"P1_LIVE_READ_ONLY_GAP_REHEARSAL",
            "status":"LIVE_ORIGINAL_ROSTER_CHECKPOINT_ARCHIVE_RECHECKED",
            "source_sha256":source,
            "active_completed_shards":initial["completed_shards"],
            "total_shards":initial["shard_count"],
            "pending_shards":len(pending),
            "proposed_manual_shards":chosen,
            "archive_index_parity_checked":True,
            "original_roster_SHA_replayed":True,
            "vendor_requests":0,
            "archive_writes":0,
            "trade_gate":"BLOCKED",
            "historical_PIT_verified":False,
            "orders":[],"executable_candidates":[],
            "permission_to_write_or_trade":False,
        }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"),required=False)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    result=rehearse(a.repo)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "status":result["status"],
        "completed":result["active_completed_shards"],
        "total":result["total_shards"],
        "manual_candidates":result["proposed_manual_shards"],
        "writes":0,"trade_gate":"BLOCKED"
    }))


if __name__=="__main__":
    main()
