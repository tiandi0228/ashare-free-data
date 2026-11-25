"""Independently rebuild a P2 catch-up receipt and its durable ledger from pinned Git trees."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from collector.p2_feature_coverage_ledger import summarize
from collector.p2_paged_real_archive import run


def _pin(root, sha):
    if re.fullmatch(r"[a-f0-9]{40}", sha) is None:
        raise ValueError("exact Git SHA required")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], timeout=30).strip()
    if git("rev-parse", "HEAD").decode() != sha or git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("checkout is not a clean pinned Git tree")


def verify(source, archive, previous, current, *, source_sha, archive_sha, previous_sha,
           current_sha, epoch, receipt_id):
    for root, sha in ((source, source_sha), (archive, archive_sha),
                      (previous, previous_sha), (current, current_sha)):
        _pin(root, sha)
    if re.fullmatch(r"[a-f0-9]{64}", epoch) is None or re.fullmatch(r"[1-9][0-9]*", receipt_id) is None:
        raise ValueError("invalid epoch or receipt ID")
    label = epoch[:16]
    def load(path):
        return json.loads(path.read_bytes())

    prior = load(previous / "summaries" / f"{label}.json")
    latest = load(current / "summaries" / f"{label}.json")
    if prior.get("source_epoch_sha256") != epoch or latest.get("source_epoch_sha256") != epoch:
        raise ValueError("coverage summaries use a different epoch")
    old = {p.name: p for p in (previous / "reports" / label).glob("*.json")}
    new = {p.name: p for p in (current / "reports" / label).glob("*.json")}
    filename = receipt_id + ".json"
    if (set(new) - set(old) != {filename}
            or any(name not in new or path.read_bytes() != new[name].read_bytes()
                   for name, path in old.items())):
        raise ValueError("expected exactly one added receipt and unchanged durable originals")
    checkpoints = source / "evidence/checkpoints"
    with TemporaryDirectory() as directory:
        replay = run(archive, checkpoints, Path(directory) / "replayed.json", coverage_summary=prior)
    if (replay.get("selection_method") != "PRIORITIZE_UNOBSERVED_ACROSS_PAGES"
            or replay.get("source_epoch_sha256") != epoch or replay != load(new[filename])):
        raise ValueError("catch-up page does not independently reproduce the durable receipt")
    rebuilt = summarize(archive / label, load(checkpoints / f"{epoch}.json"),
                        [load(new[name]) for name in sorted(new)])
    if rebuilt.get("status") != "DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED" or rebuilt != latest:
        raise ValueError("durable coverage summary does not reproduce")
    return {
        "status": "CATCHUP_RECEIPT_AND_SUMMARY_REPRODUCED_RESEARCH_ONLY",
        "receipt_run_id": receipt_id, "selected_shards": replay["selected_shards"],
        "computed_features": replay["computed_feature_issuers"], "reports_replayed": len(new),
        "feature_complete_shards": rebuilt["feature_complete_shards"],
        "observed_archived_shards": rebuilt["observed_archived_shards"],
        "issuer_evidence_gap_count": rebuilt["issuer_evidence_gap_count"],
        "historical_PIT_verified": False, "trade_gate": "BLOCKED", "orders": [],
        "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("source", "archive", "previous", "current"):
        parser.add_argument("--" + key, type=Path, required=True)
        parser.add_argument("--" + key + "-sha", required=True)
    parser.add_argument("--epoch", required=True)
    parser.add_argument("--receipt-id", required=True)
    print(json.dumps(verify(**vars(parser.parse_args())), indent=2))


if __name__ == "__main__":
    main()
