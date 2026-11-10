"""Read-only independent target byte replay against a source SHA handoff.

Does not copy, delete, authorize migration, validate source authenticity or
certify historical PIT. The handoff must first be sealed and independently
source-replayed by the existing P1 origin pipeline.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r"[a-f0-9]{64}\Z")
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
FILE = re.compile(r"[a-f0-9]{16}/shard_[0-9]{4}/(?:quality[.]json|(?:sh|sz)_[0-9]{6}[.]csv)\Z")
STATUS = re.compile(r"[a-f0-9]{16}/archive_status[.]json\Z")
MAX_FILES = 24 * 400 * 9


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def reconcile(handoff, target, target_commit):
    if not isinstance(target_commit, str) or not COMMIT.fullmatch(target_commit):
        raise ValueError("destination commit must be an immutable Git SHA")
    if (not isinstance(handoff, dict)
        or handoff.get("phase") != "P1_SOURCE_SHA_HANDOFF_NO_DESTINATION_ATTESTATION"
        or handoff.get("status") != "SOURCE_MANIFEST_REPLAYED_TARGET_UNVERIFIED"
        or handoff.get("canonical_inventory_format") != "JSON_SORT_KEYS_COMPACT_UTF8_SORTED_BY_PATH"
        or handoff.get("source_manifest_has_no_archive_status_files") is not True
        or any(handoff.get(k) is not False for k in (
            "destination_files_verified", "migration_performed",
            "automatic_copy_authorized", "writer_cutover_authorized",
            "historical_PIT_verified"))
        or handoff.get("trade_gate") != "BLOCKED"
        or handoff.get("orders") != []
        or handoff.get("executable_candidates") != []):
        raise ValueError("untrusted source-only handoff")
    rows = handoff.get("original_paths_and_sha256")
    digest = handoff.get("source_file_inventory_sha256")
    if (not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILES
        or type(handoff.get("eligible_original_files")) is not int
        or len(rows) != handoff["eligible_original_files"]
        or not isinstance(digest, str) or not SHA.fullmatch(digest)):
        raise ValueError("invalid handoff inventory size or checksum")
    expected = {}
    previous = ""
    for row in rows:
        path = row.get("path") if isinstance(row, dict) else None
        hash_value = row.get("sha256") if isinstance(row, dict) else None
        if (not isinstance(path, str) or not FILE.fullmatch(path)
            or path <= previous or not isinstance(hash_value, str)
            or not SHA.fullmatch(hash_value)):
            raise ValueError("unsafe or duplicate source handoff path")
        previous = path
        expected[path] = hash_value
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(canonical).hexdigest() != digest:
        raise ValueError("source handoff canonical digest mismatch")
    root = Path(target)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("destination root missing or symlinked")
    observed = {}
    status_paths = []
    unexpected = []
    for entry in sorted(root.rglob("*")):
        rel = entry.relative_to(root).as_posix()
        if ".git" in entry.relative_to(root).parts:
            continue
        if entry.is_symlink():
            raise ValueError("destination symlink forbidden")
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise ValueError("destination nonregular entry")
        if FILE.fullmatch(rel):
            observed[rel] = sha256(entry)
        elif STATUS.fullmatch(rel):
            # Status receipts are outside the source handoff; never count
            # them as SHA-certified source originals.
            status_paths.append(rel)
        else:
            unexpected.append(rel)
    matching = sorted(path for path, val in observed.items()
                      if expected.get(path) == val)
    conflicts = sorted(path for path, val in observed.items()
                       if path in expected and expected[path] != val)
    not_allowlisted = sorted(path for path in observed if path not in expected)
    missing = sorted(path for path in expected if path not in observed)
    status = ("TARGET_CONFLICT_OR_UNALLOWLISTED" if conflicts or not_allowlisted or unexpected else
              "TARGET_PARTIAL_SOURCE_HANDOFF_READBACK" if missing else
              "TARGET_BYTES_MATCH_SOURCE_HANDOFF_NOT_CERTIFIED")
    return {
        "phase": "P1_PRIVATE_TARGET_SOURCE_HANDOFF_SHA_READBACK",
        "status": status,
        "source_file_inventory_sha256": digest,
        "target_commit": target_commit,
        "allowlisted_files": len(expected),
        "matching_file_count": len(matching),
        "missing_file_count": len(missing),
        "conflicting_file_count": len(conflicts),
        "unallowlisted_target_file_count": len(not_allowlisted) + len(unexpected),
        "separate_unverified_status_file_count": len(status_paths),
        "missing_file_sample": missing[:20],
        "conflicting_file_sample": conflicts[:20],
        "unallowlisted_file_sample": sorted(not_allowlisted + unexpected)[:20],
        "destination_files_verified": False,
        "destination_mirror_verified": False,
        "source_hand_off_sealed_and_replayed_independently": False,
        "migration_performed": False,
        "automatic_copy_authorized": False,
        "writer_cutover_authorized": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--handoff", required=True, type=Path)
    p.add_argument("--target", required=True, type=Path)
    p.add_argument("--target-commit", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = reconcile(json.loads(args.handoff.read_text()),
                       args.target, args.target_commit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "status", "allowlisted_files", "matching_file_count",
        "missing_file_count", "conflicting_file_count",
        "unallowlisted_target_file_count", "trade_gate"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
