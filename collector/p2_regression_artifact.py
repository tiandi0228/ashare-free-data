"""Verify a downloaded P2 regression artifact against its reports and explanation pin."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from collector.p2_gap_disposition import compare

REPLAY = "p2-pinned-replay.json"
DISPOSITION = "p2-pinned-disposition.json"
RECEIPT = "p2-pinned-run-receipt.json"
LIMIT = 256 * 1024


def verify(path, pinned, *, expected_archive_commit, expected_run_id=None):
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if (len(entries) != 3 or {e.filename for e in entries} != {REPLAY, DISPOSITION, RECEIPT}
                or any(e.file_size > LIMIT for e in entries)):
            raise ValueError("unexpected regression archive contents")
        raw = {e.filename: archive.read(e) for e in entries}
    receipt = json.loads(raw[RECEIPT])
    if (receipt.get("kind") != "PINNED_ARCHIVE_REGRESSION_NOT_LIVE_COVERAGE"
            or receipt.get("archive_commit") != expected_archive_commit
            or (expected_run_id is not None and receipt.get("github_run_id") != expected_run_id)
            or receipt.get("trade_gate") != "BLOCKED"
            or receipt.get("historical_PIT_verified") is not False):
        raise ValueError("regression receipt scope mismatch")
    hashes = {name: hashlib.sha256(raw[name]).hexdigest() for name in (REPLAY, DISPOSITION)}
    if receipt.get("report_sha256") != hashes:
        raise ValueError("regression report SHA-256 mismatch")
    rebuilt = compare(json.loads(raw[REPLAY]), pinned)
    if rebuilt != json.loads(raw[DISPOSITION]):
        raise ValueError("disposition replay mismatch")
    for key in ("asof", "source_epoch_sha256", "explained_feature_unavailable",
                "review_required", "feature_gaps_resolved"):
        if receipt.get(key) != rebuilt[key]:
            raise ValueError(f"receipt summary mismatch: {key}")
    return dict(status="REPORTS_AND_DISPOSITION_VERIFIED", archive_commit=expected_archive_commit,
                github_run_id=receipt["github_run_id"], asof=rebuilt["asof"],
                explained=rebuilt["explained_feature_unavailable"], review_required=rebuilt["review_required"],
                feature_gaps_resolved=0, trade_gate="BLOCKED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--archive-commit", required=True)
    parser.add_argument("--run-id")
    a = parser.parse_args()
    print(json.dumps(verify(a.archive, json.loads(a.pin.read_bytes()),
                            expected_archive_commit=a.archive_commit, expected_run_id=a.run_id)))


if __name__ == "__main__":
    main()
