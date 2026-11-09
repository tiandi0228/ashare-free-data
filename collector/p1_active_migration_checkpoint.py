"""Choose a strictly validated same-commit P1 checkpoint for read-only archive auditing."""
import argparse
import json
from pathlib import Path
from collector.p1_checkpoint import epoch_path, validate
from collector.p1_roster_lock import unpack

def resolve(root):
    root = Path(root)
    lock = json.loads((root / "evidence/p1_active_roster.json").read_text())
    unpack(lock)
    digest = lock["source_sha256"]
    rel = epoch_path(digest)
    checkpoint = validate(json.loads((root / rel).read_text()))
    if checkpoint["source_sha256"] != digest:
        raise ValueError("active roster/checkpoint epoch mismatch")
    return {"source_sha256": digest, "checkpoint_path": rel,
            "completed_shards": checkpoint["completed_shards"],
            "completed_issuers": checkpoint["completed_issuers"],
            "total_shards": checkpoint["shard_count"],
            "trade_gate": "BLOCKED", "historical_PIT_verified": False,
            "writer_cutover_authorized": False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--github-output", type=Path)
    args = p.parse_args()
    result = resolve(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+"\n")
    if args.github_output:
        with args.github_output.open("a") as out:
            out.write("checkpoint_path="+result["checkpoint_path"]+"\n")
            out.write("source_epoch="+result["source_sha256"]+"\n")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
