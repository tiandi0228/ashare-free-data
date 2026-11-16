"""Read-only verification of a completed single-shard P1 manual acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from collector.p1_checkpoint import validate


WORKFLOW = ".github/workflows/p1-fresh-vendor-roster.yml"


def verify(run, receipt, live, quality, archive_status, read_csv, *, shard, workflow_sha, archive_sha):
    """Bind the artifact to the exact run attempt and independently read archive state."""
    validate(live)
    if (type(shard) is not int or not 0 <= shard < live["shard_count"]
            or any(not re.fullmatch(r"[a-f0-9]{40}", s) for s in (workflow_sha, archive_sha))):
        raise ValueError("invalid expected shard or Git commit")
    if (run.get("event") != "workflow_dispatch" or run.get("path") != WORKFLOW
            or run.get("head_branch") != "main" or run.get("head_sha") != workflow_sha
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or type(run.get("id")) is not int or run["id"] <= 0
            or type(run.get("run_attempt")) is not int or run["run_attempt"] <= 0):
        raise ValueError("not the expected successful main workflow attempt")
    if (receipt.get("status") != "MANUAL_GAP_ARCHIVE_AND_CHECKPOINT_VERIFIED"
            or receipt.get("run_id") != str(run["id"])
            or receipt.get("run_attempt") != str(run["run_attempt"])
            or receipt.get("workflow_sha") != workflow_sha
            or receipt.get("archive_audit_commit") != archive_sha
            or receipt.get("source_sha256") != live["source_sha256"]
            or receipt.get("selected_shards") != [shard]
            or receipt.get("new_shards_durably_accepted") != 1
            or receipt.get("remote_readback_verified") is not True
            or receipt.get("historical_PIT_verified") is not False
            or receipt.get("trade_gate") != "BLOCKED"
            or receipt.get("orders") != [] or receipt.get("executable_candidates") != []
            or not re.fullmatch(r"[0-9a-f]{40}", receipt.get("checkpoint_blob_sha", ""))):
        raise ValueError("manual acceptance receipt does not match run or shard")
    done = {row["index"]: row for row in live["completed"]}
    accepted = done.get(shard)
    archived_quality = json.loads(quality)
    canonical = json.dumps(archived_quality, sort_keys=True, ensure_ascii=False).encode()
    if (accepted is None or receipt.get("accepted_shards") != [accepted]
            or hashlib.sha256(canonical).hexdigest() != accepted["receipt_sha256"]):
        raise ValueError("shard archive receipt is missing or differs from live checkpoint")
    rows = archived_quality["results"]
    codes = [row["code"] for row in rows]
    if (archived_quality.get("trade_gate") != "BLOCKED"
            or archived_quality.get("status") != "OBSERVED_SUBSET_UNVERIFIED"
            or len(codes) != accepted["issuer_count"] or len(set(codes)) != len(codes)
            or any(re.fullmatch(r"(sh|sz)\.[0-9]{6}", code) is None for code in codes)
            or hashlib.sha256("".join(code + "\n" for code in sorted(codes)).encode()).hexdigest()
            != accepted["manifest_sha256"]
            or archived_quality.get("manifest_sha256") != accepted["manifest_sha256"]
            or any(row.get("status") != "OBSERVED_UNVERIFIED"
                   or hashlib.sha256(read_csv(row["code"])).hexdigest() != row["sha256"] for row in rows)):
        raise ValueError("archive issuer membership or original CSV digest differs")
    archived = archive_status.get("archived_shards")
    if (archive_status.get("trade_gate") != "BLOCKED"
            or archive_status.get("source_sha256") != live["source_sha256"]
            or not isinstance(archived, list)
            or any(type(n) is not int for n in archived)
            or len(archived) != len(done) or set(archived) != set(done)):
        raise ValueError("live archive and checkpoint indices differ")
    return {"status": "SINGLE_SHARD_MANUAL_ACCEPTANCE_READBACK_VERIFIED",
            "shard": shard, "run_id": run["id"], "run_attempt": run["run_attempt"],
            "source_sha256": live["source_sha256"], "live_completed_shards": len(done),
            "trade_gate": "BLOCKED", "historical_PIT_verified": False,
            "orders": [], "executable_candidates": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("run", "receipt", "live", "quality", "archive-status"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--archive-sha", required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_bytes())
    print(json.dumps(verify(load(args.run), load(args.receipt), load(args.live),
                            args.quality.read_bytes(), load(args.archive_status),
                            lambda code: (args.quality.parent / (code.replace(".", "_") + ".csv")).read_bytes(),
                            shard=args.shard, workflow_sha=args.workflow_sha,
                            archive_sha=args.archive_sha), indent=2))


if __name__ == "__main__":
    main()
