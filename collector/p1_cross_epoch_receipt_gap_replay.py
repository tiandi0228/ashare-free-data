"""Read-only SHA comparison of legacy receipt gaps versus another archived epoch.

A byte match is not the missing original quality.json, nor proof of PIT/source
authenticity. Never rewrite a historical file or authorize migration/trading.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{64}\Z")
CODE = re.compile(r"(?:sh|sz)_[0-9]{6}\.csv\Z")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def safe_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing or unsafe source file: " + str(path))
    return path


def audit(root, legacy_sha, comparison_sha, indices=(24, 25)):
    root = Path(root)
    if any(not isinstance(s, str) or not SHA.fullmatch(s) for s in (legacy_sha, comparison_sha)):
        raise ValueError("invalid source epoch SHA")
    if legacy_sha == comparison_sha:
        raise ValueError("must compare distinct source epochs")
    if not indices or len(indices) != len(set(indices)) or any(type(i) is not int or not 0 <= i < 10000 for i in indices):
        raise ValueError("invalid shard indices")
    report = {
        "phase": "P1_CROSS_EPOCH_ORIGINAL_CSV_SHA_DIAGNOSTIC",
        "status": "UNVERIFIED",
        "legacy_source_sha256": legacy_sha,
        "comparison_source_sha256": comparison_sha,
        "shards": [],
        "compared_files": 0,
        "matching_files": 0,
        "different_files": 0,
        "missing_comparison_files": 0,
        "missing_original_receipts_recovered": 0,
        "legacy_receipts_authenticated": False,
        "historical_PIT_verified": False,
        "source_archive_sha_verified": False,
        "destination_mirror_verified": False,
        "writer_cutover_authorized": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }
    epochs = []
    for source in (legacy_sha, comparison_sha):
        epoch = root / source[:16]
        if epoch.is_symlink() or not epoch.is_dir():
            raise ValueError("missing or unsafe archive epoch")
        marker = json.loads(safe_file(epoch / "archive_status.json").read_text())
        advertised = marker.get("archived_shards")
        if marker.get("source_sha256") != source or marker.get("trade_gate") != "BLOCKED" or not isinstance(advertised, list) or len(advertised) != len(set(advertised)) or any(type(i) is not int for i in advertised):
            raise ValueError("invalid source archive status")
        epochs.append((epoch, set(advertised)))
    (old, old_ids), (new, new_ids) = epochs
    for index in sorted(indices):
        if index not in old_ids:
            raise ValueError("legacy status did not advertise requested shard")
        old_shard = old / f"shard_{index:04d}"
        if old_shard.is_symlink() or not old_shard.is_dir():
            raise ValueError("missing or unsafe legacy shard")
        old_receipt = old_shard / "quality.json"
        if old_receipt.is_symlink() or old_receipt.exists():
            raise ValueError("legacy original receipt is present or unsafe; not a missing-receipt case")
        old_files = sorted(old_shard.iterdir())
        if not old_files or any(f.is_symlink() or not f.is_file() or not CODE.fullmatch(f.name) for f in old_files):
            raise ValueError("unexpected legacy shard members")
        row = {"shard_index": index, "legacy_original_receipt_present": False, "comparison_receipt_present": False, "files": []}
        new_shard = new / f"shard_{index:04d}"
        if index in new_ids and new_shard.is_dir() and not new_shard.is_symlink():
            new_receipt = new_shard / "quality.json"
            if new_receipt.is_symlink():
                raise ValueError("unsafe comparison receipt")
            if new_receipt.is_file():
                receipt = json.loads(safe_file(new_receipt).read_text())
                results = receipt.get("results")
                if receipt.get("trade_gate") != "BLOCKED" or receipt.get("status") != "OBSERVED_SUBSET_UNVERIFIED" or not isinstance(results, list):
                    raise ValueError("invalid comparison receipt")
                digest_map = {}
                for result in results:
                    code, digest = result.get("code"), result.get("sha256")
                    if not isinstance(code, str) or not isinstance(digest, str) or not SHA.fullmatch(digest):
                        raise ValueError("invalid comparison receipt row")
                    name = code.replace(".", "_") + ".csv"
                    if not CODE.fullmatch(name) or name in digest_map:
                        raise ValueError("invalid comparison receipt issuer")
                    digest_map[name] = digest
                row["comparison_receipt_present"] = True
                for f in old_files:
                    old_digest = sha256(f)
                    target = new_shard / f.name
                    item = {"filename": f.name, "legacy_sha256": old_digest, "comparison_sha256": None, "comparison_receipt_sha256": digest_map.get(f.name), "result": "COMPARISON_NOT_AVAILABLE"}
                    if f.name in digest_map and target.is_file() and not target.is_symlink():
                        new_digest = sha256(target)
                        item["comparison_sha256"] = new_digest
                        report["compared_files"] += 1
                        if new_digest != digest_map[f.name]:
                            item["result"] = "COMPARISON_RECEIPT_SHA_MISMATCH"
                            report["different_files"] += 1
                        elif new_digest == old_digest:
                            item["result"] = "BYTES_MATCH_NOT_LEGACY_PROVENANCE"
                            report["matching_files"] += 1
                        else:
                            item["result"] = "BYTES_DIFFER"
                            report["different_files"] += 1
                    else:
                        report["missing_comparison_files"] += 1
                    row["files"].append(item)
        if not row["files"]:
            for f in old_files:
                row["files"].append({"filename": f.name, "legacy_sha256": sha256(f), "comparison_sha256": None, "comparison_receipt_sha256": None, "result": "COMPARISON_NOT_AVAILABLE"})
                report["missing_comparison_files"] += 1
        report["shards"].append(row)
    report["status"] = "CROSS_EPOCH_DIAGNOSTIC_ONLY"
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--legacy-sha", required=True)
    p.add_argument("--comparison-sha", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = audit(args.archive, args.legacy_sha, args.comparison_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "shards"}))


if __name__ == "__main__":
    main()
