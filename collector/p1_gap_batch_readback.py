"""Independently compare two pinned P1 states; never attribute a change to a run."""
import argparse
import json
from pathlib import Path
import subprocess

from collector.p1_checkpoint import epoch_path
from collector.p1_gap_batch_queue import from_git


def compare(prior, current, before, after, selected):
    if (prior["source_sha256"] != current["source_sha256"]
            or prior["total_shards"] != current["total_shards"]
            or not prior["archive_original_csvs_replayed"] or not current["archive_original_csvs_replayed"]):
        raise ValueError("both states must replay the same frozen roster and original CSVs")
    if (not 1 <= len(selected) <= 2 or len(set(selected)) != len(selected)
            or any(type(i) is not int or not 0 <= i < prior["total_shards"] or i in before
                   for i in selected)):
        raise ValueError("select one or two distinct previously missing shards")
    if (len(before) != prior["completed_shards"] or len(after) != current["completed_shards"]
            or any(after.get(i) != receipt for i, receipt in before.items())):
        raise ValueError("previous checkpoint receipts were lost or changed")
    added = set(after) - set(before)
    accepted = [i for i in selected if i in added]
    return {
        "status": ("ALL_SELECTED_DURABLY_PRESENT" if len(accepted) == len(selected)
                   else "SOME_SELECTED_DURABLY_PRESENT" if accepted else "NO_SELECTED_SHARD_DURABLY_PRESENT"),
        "source_sha256": prior["source_sha256"],
        "previous_shards": len(before), "current_shards": len(after),
        "total_shards": current["total_shards"],
        "selected": selected, "selected_durably_present": accepted,
        "selected_still_missing": [i for i in selected if i not in added],
        "unrelated_new_shards": sorted(added - set(selected)),
        "workflow_run_attribution_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def readback(repo, main_before, main_after, archive_before, archive_after,
             checkout_before, checkout_after, selected):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], timeout=30)

    base = from_git(repo, main_before, archive_before, replay_checkout=checkout_before)
    head = from_git(repo, main_after, archive_after, replay_checkout=checkout_after)
    source = base["source_sha256"]
    epoch = source[:16]
    if head["source_sha256"] != source:
        raise ValueError("active frozen roster changed")
    for old, new in ((main_before, main_after), (archive_before, archive_after)):
        git("merge-base", "--is-ancestor", old, new)
    # Original archive files may only be added, not replaced or removed.
    diff = git("diff", "--no-renames", "--name-status", archive_before, archive_after,
               "--", f"{epoch}/").decode().splitlines()
    for line in diff:
        mode, path = line.split("\t", 1)
        if path != f"{epoch}/archive_status.json" and mode != "A":
            raise ValueError("existing archive original changed")
    def receipts(commit):
        ledger = json.loads(git("show", f"{commit}:{epoch_path(source)}"))
        return {row["index"]: row for row in ledger["completed"]}
    result = compare(base, head, receipts(main_before), receipts(main_after), selected)
    return {**result, "main_before": main_before, "main_after": main_after,
            "archive_before": archive_before, "archive_after": archive_after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    for key in ("main-before", "main-after", "archive-before", "archive-after"):
        parser.add_argument("--" + key, required=True)
    for key in ("checkout-before", "checkout-after"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--selected", type=int, nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps(readback(**vars(args)), indent=2))


if __name__ == "__main__":
    main()
