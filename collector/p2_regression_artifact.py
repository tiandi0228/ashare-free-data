"""Verify a downloaded P2 regression artifact against its reports and explanation pin."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from collector.p2_gap_disposition import compare

REPLAY = "p2-pinned-replay.json"
DISPOSITION = "p2-pinned-disposition.json"
RECEIPT = "p2-pinned-run-receipt.json"
LIMIT = 256 * 1024


def verify(path, pinned, *, expected_archive_commit, expected_run_id,
           expected_run_attempt, expected_tested_commit, expected_zip_sha256):
    # Hash and parse the same bytes. The digest must come from the Actions
    # artifact metadata, not from the receipt inside the downloaded ZIP.
    with Path(path).open("rb") as stream:
        package = stream.read(4 * LIMIT + 1)
    if len(package) > 4 * LIMIT:
        raise ValueError("regression ZIP exceeds size limit")
    zip_sha256 = hashlib.sha256(package).hexdigest()
    if zip_sha256 != expected_zip_sha256.removeprefix("sha256:"):
        raise ValueError("regression ZIP SHA-256 mismatch")
    with ZipFile(BytesIO(package)) as archive:
        entries = archive.infolist()
        if (len(entries) != 3 or {e.filename for e in entries} != {REPLAY, DISPOSITION, RECEIPT}
                or any(e.file_size > LIMIT for e in entries)):
            raise ValueError("unexpected regression archive contents")
        raw = {e.filename: archive.read(e) for e in entries}
    receipt = json.loads(raw[RECEIPT])
    if (receipt.get("kind") != "PINNED_ARCHIVE_REGRESSION_NOT_LIVE_COVERAGE"
            or receipt.get("archive_commit") != expected_archive_commit
            or receipt.get("github_run_id") != expected_run_id
            or receipt.get("github_run_attempt") != expected_run_attempt
            or receipt.get("tested_commit") != expected_tested_commit
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
                tested_commit=expected_tested_commit, github_run_id=expected_run_id,
                github_run_attempt=expected_run_attempt, zip_sha256=zip_sha256, asof=rebuilt["asof"],
                explained=rebuilt["explained_feature_unavailable"], review_required=rebuilt["review_required"],
                feature_gaps_resolved=0, trade_gate="BLOCKED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--archive-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--tested-commit", required=True,
                        help="Exact checkout SHA, normally the pull request merge commit, not the PR head")
    parser.add_argument("--zip-sha256", required=True, help="Digest from Actions artifact metadata")
    a = parser.parse_args()
    print(json.dumps(verify(a.archive, json.loads(a.pin.read_bytes()),
                            expected_archive_commit=a.archive_commit, expected_run_id=a.run_id,
                            expected_run_attempt=a.run_attempt, expected_tested_commit=a.tested_commit,
                            expected_zip_sha256=a.zip_sha256)))


if __name__ == "__main__":
    main()
