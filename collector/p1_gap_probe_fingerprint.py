"""Compare research probe fingerprints with independently verified shard receipts."""
import argparse
import json
from pathlib import Path
import re


def fingerprint(receipt):
    manifest = receipt["manifest_sha256"]
    rows = receipt["results"]
    if (receipt.get("trade_gate") != "BLOCKED" or not re.fullmatch(r"[0-9a-f]{64}", manifest)
            or not 1 <= len(rows) <= 8 or receipt.get("issuer_count") != len(rows)):
        raise ValueError("invalid verified shard receipt")
    hashes = {}
    for row in rows:
        code, digest = row["code"], row["sha256"]
        if (not re.fullmatch(r"(?:sh|sz)\.[0-9]{6}", code) or code in hashes
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or row.get("status") != "OBSERVED_UNVERIFIED"):
            raise ValueError("invalid verified issuer fingerprint")
        hashes[code] = digest
    return {"manifest_sha256": manifest, "csv_sha256_by_issuer": hashes}


def compare(probe, later):
    current = fingerprint(later)
    original = probe["csv_sha256_by_issuer"]
    hashes = current["csv_sha256_by_issuer"]
    if (probe["manifest_sha256"] != current["manifest_sha256"]
            or original.keys() != hashes.keys()
            or any(not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
                   for v in original.values())):
        raise ValueError("manifest or issuer fingerprints do not match")
    changed = sorted(code for code in original if original[code] != hashes[code])
    return {
        "status": "SOURCE_BYTES_DIFFER_REVIEW" if changed else "CSV_DIGESTS_MATCH",
        "changed_issuers": changed, "matching_count": len(hashes) - len(changed),
        "archive_acceptance_verified": False, "trade_gate": "BLOCKED",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe", type=Path, required=True)
    p.add_argument("--quality", type=Path, required=True)
    p.add_argument("--shard", type=int, required=True)
    args = p.parse_args()
    probe = json.loads(args.probe.read_bytes())
    entries = [item for item in probe["verified"] if item["index"] == args.shard]
    if len(entries) != 1 or probe.get("trade_gate") != "BLOCKED":
        raise ValueError("expected one verified probe entry for shard")
    print(json.dumps(compare(entries[0], json.loads(args.quality.read_bytes())), indent=2))


if __name__ == "__main__":
    main()
