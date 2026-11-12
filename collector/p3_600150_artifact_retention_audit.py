"""Bounded P3 artifact retention gate: metadata pin is NOT durable PDF archival.

Query two exact GitHub artifact metadata endpoints. Refuse changed ZIP digests,
IDs, missing/expired artifacts or forged official/PIT/trading claims.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{64}\Z")
UTC = timezone.utc


def instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(None):
        raise ValueError("expected UTC timestamp")
    return parsed.astimezone(UTC)


def audit(manifest, remote, *, at):
    now = instant(at)
    if (not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("phase") != "P3_600150_TEMPORARY_RESEARCH_ARTIFACT_RETENTION"
        or manifest.get("issuer") != "sh.600150"
        or manifest.get("repository") != "tiandi0228/ashare-free-data"
        or manifest.get("historical_first_publication_authenticated") is not False
        or manifest.get("official_issuer_state_certified") is not False
        or manifest.get("original_pdf_bytes_in_permanent_archive") is not False
        or manifest.get("trade_gate") != "BLOCKED"
        or manifest.get("orders") != []
        or manifest.get("executable_candidates") != []):
        raise ValueError("unsafe research retention declaration")
    frozen = {
        13905959428: ("43134271671", "fc1906b93b05f794db37f1084a49d256e2ac8219500995b923a8e9aa099285a1",
                       "2026-12-12T01:24:22Z", {
                           "1224387134": ("498e48ccc9651e9be9e32dd17eaf60e2e9b9ed43fc8be41b26c995308561a66e", 92093),
                           "1224504273": ("a529af260766407070b8d800cb890b26d06bee07adca3192244fe225546a1dbe", 89199),
                       }),
        13908412596: ("43139104789", "313430fe462d98307a7474f17b28bdff7cef8bced313077c31be97b772c55b07",
                       "2026-12-12T02:06:54Z", {
                           "SSE_DAILY_MIRROR_20250818": ("9051ffc0413331c7864c78e6066e57ad2d18c026c48a4c5fed4aae828c758d16", 34854),
                       }),
    }
    entries = manifest.get("artifacts")
    if not isinstance(entries, list) or len(entries) != 2:
        raise ValueError("wrong artifact count")
    if not isinstance(remote, list) or len(remote) != 2:
        raise ValueError("missing remote artifact metadata")
    lookup = {}
    for row in remote:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] in lookup:
            raise ValueError("duplicate or wrong remote ID")
        lookup[row["id"]] = row
    if set(lookup) != set(frozen):
        raise ValueError("unexpected remote artifacts")
    count = 0
    total_bytes = 0
    seen = set()
    nearest = None
    for entry in entries:
        if not isinstance(entry, dict) or type(entry.get("artifact_id")) is not int:
            raise ValueError("invalid artifact declaration")
        aid = entry["artifact_id"]
        if aid in seen or aid not in frozen:
            raise ValueError("duplicate or unpinned artifact")
        seen.add(aid)
        run_id, sha, expiry, pdfs = frozen[aid]
        expected = {
            "artifact_id": aid,
            "source_run_id": int(run_id),
            "artifact_zip_sha256": sha,
            "expires_at": expiry,
        }
        for k, value in expected.items():
            if type(entry.get(k)) is not type(value) or entry[k] != value:
                raise ValueError("changed frozen artifact manifest")
        originals = entry.get("pdf_originals")
        if not isinstance(originals, list) or len(originals) != len(pdfs):
            raise ValueError("missing PDF originals")
        observed = {}
        for item in originals:
            if not isinstance(item, dict):
                raise ValueError("invalid original")
            ident = item.get("announcement_id")
            if ident not in pdfs or ident in observed:
                raise ValueError("wrong original identity")
            observed[ident] = item
            expected_digest, expected_size = pdfs[ident]
            if (item.get("sha256") != expected_digest
                or type(item.get("bytes")) is not int
                or item["bytes"] != expected_size):
                raise ValueError("wrong frozen original SHA or bytes")
            count += 1
            total_bytes += expected_size
        if set(observed) != set(pdfs):
            raise ValueError("incomplete original list")
        live = lookup[aid]
        if (live.get("expired") is not False or
            live.get("digest") != "sha256:" + sha or
            live.get("expires_at") != expiry or
            not isinstance(live.get("workflow_run"), dict) or
            live["workflow_run"].get("id") != int(run_id)):
            raise ValueError("artifact expired or remote provenance changed")
        exp = instant(live["expires_at"])
        if now >= exp:
            raise ValueError("artifact retention expired at audit instant")
        nearest = exp if nearest is None else min(nearest, exp)
    return {
        "phase": "P3_600150_TEMPORARY_ARTIFACT_RETENTION_AUDIT",
        "artifact_count": len(seen),
        "original_pdf_count": count,
        "original_pdf_bytes_frozen": total_bytes,
        "earliest_expiry_utc": nearest.isoformat(),
        "days_to_first_expiry_floor": (nearest - now).days,
        "original_pdf_bytes_in_permanent_archive": False,
        "historical_first_publication_authenticated": False,
        "official_issuer_state_certified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-metadata", required=True, type=Path)
    parser.add_argument("--daily-metadata", required=True, type=Path)
    parser.add_argument("--asof-utc", required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    records = [json.loads(path.read_text()) for path in
               (args.source_metadata, args.daily_metadata)]
    result = audit(data, records, at=args.asof_utc)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
