"""Compare research probe fingerprints with independently verified shard receipts."""
import argparse
import hashlib
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


PROBE_RUN_ID = 43820286717
PROBE_ARTIFACT_ID = 14204680816
PROBE_JSON_SHA256 = "625e4d4091157a08b80345fcfde2cbbcd107afe0cdd7e510b7ecc37d3a762570"


def compare_historical_probe(raw, readback, quality, frozen, manifests):
    """Compare one historical probe to an independently replayed archive snapshot."""
    if hashlib.sha256(raw).hexdigest() != PROBE_JSON_SHA256:
        raise ValueError("historical probe JSON digest mismatch")
    probe = json.loads(raw)
    if (probe["attempted"] != [231, 232] or [row["index"] for row in probe["verified"]] != [231, 232]
            or probe["archive_writes"] != 0 or probe["checkpoint_writes"] != 0
            or probe["trade_gate"] != "BLOCKED" or probe["historical_PIT_verified"] is not False
            or probe["orders"] != [] or readback["trade_gate"] != "BLOCKED"
            or readback["selected_durably_present"] != [231]
            or readback["selected_still_missing"] != [232]
            or readback["source_sha256"] != frozen["source_sha256"]):
        raise ValueError("historical probe and archive scope disagree")
    for entry in probe["verified"]:
        shard = frozen["shards"][entry["index"]]
        blob = (manifests / shard["name"]).read_bytes()
        if (hashlib.sha256(blob).hexdigest() != shard["sha256"]
                or entry["manifest_sha256"] != shard["sha256"]
                or entry["issuers"] != shard["count"]
                or sorted(entry["csv_sha256_by_issuer"]) != blob.decode().splitlines()
                or any(re.fullmatch(r"[0-9a-f]{64}", value) is None
                       for value in entry["csv_sha256_by_issuer"].values())):
            raise ValueError("probe fingerprint does not match frozen shard membership")
    match = compare(probe["verified"][0], quality)
    if match["status"] != "CSV_DIGESTS_MATCH":
        raise ValueError("archived shard CSV digest differed from historical probe")
    return {
        "probe_run_id": PROBE_RUN_ID, "probe_artifact_id": PROBE_ARTIFACT_ID,
        "probe_json_sha256": PROBE_JSON_SHA256, "source_sha256": frozen["source_sha256"],
        "archive_commit": readback["archive_after"], "checkpoint_commit": readback["main_after"],
        "archived_shard": 231, "archived_csv_digests_matching_probe": match["matching_count"],
        "probe_only_shard": 232, "probe_only_issuer_fingerprints": probe["verified"][1]["issuers"],
        "probe_only_shard_archive_acceptance_verified": False,
        "workflow_run_attribution_verified": False, "trade_gate": "BLOCKED",
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
