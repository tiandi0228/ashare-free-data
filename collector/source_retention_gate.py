"""Evidence-retention readiness gate: actual GitHub Artifact API facts, not SHA hopes.

No market data, no cloud warehouse, no licensed-data redistribution.
Source SHA metadata alone is never a permanent raw-byte archive.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

REPO = "tiandi0228/ashare-free-data"
EXPECTED = {
    39572697952: 12331524968,
    39573265839: 12333180646,
    39589103403: 12340239649,
    39602222641: 12346189195,
}
EXPLICIT_NO_RAW_ORIGINAL = (
    "baostock_lifecycle_9018_rows_sha_only",
    "cninfo_600421_2026_05_23_pdf_sha_only",
    "cninfo_600421_2026_06_19_pdf_sha_only",
)
MAX_GITHUB_PUBLIC_DAYS = 90


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def parse_utc(value):
    require(isinstance(value, str) and value.endswith("Z"),
            "Expected UTC ISO8601 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid source UTC timestamp") from exc


def audit(inventory, original16, delisted8, historical_st):
    require(inventory.get("repository") == REPO,
            "Wrong public source repository")
    now = parse_utc(inventory.get("inspected_at_utc"))
    require(original16.get("capture_run_ids") == [39572697952, 39573265839] and
            original16.get("capture_artifact_ids") == [12331524968, 12333180646] and
            original16.get("audit_report", {}).get("original_source_rows") == 7760 and
            original16.get("audit_report", {}).get("trade_gate") == "BLOCKED",
            "P1 sixteen-source original provenance has changed")
    require(delisted8.get("source_run_id") == 39589103403 and
            delisted8.get("original_data_artifact_id") == 12340239649 and
            delisted8.get("replay_report", {}).get("original_csv_total_rows") == 3803 and
            delisted8.get("trade_gate") == "BLOCKED",
            "P1 eight-source original provenance has changed")
    require(historical_st.get("acquisition_run_id") == 39602222641 and
            historical_st.get("acquisition_artifact_id") == 12346189195 and
            historical_st.get("verified_vendor_source_replay", {}).get("total_source_rows") == 536 and
            historical_st.get("trade_gate") == "BLOCKED",
            "P3 two-source original ST provenance has changed")
    runs = inventory.get("runs")
    require(isinstance(runs, list) and len(runs) == len(EXPECTED),
            "Missing, unexpected or duplicated source capture runs")
    seen_runs = set()
    records = []
    for run in runs:
        run_id = run.get("run_id")
        require(type(run_id) is int and run_id in EXPECTED and
                run_id not in seen_runs, "Unrecognized or repeated source run")
        seen_runs.add(run_id)
        artifacts = run.get("artifacts")
        require(isinstance(artifacts, list),
                "Source artifact inventory missing")
        matches = [x for x in artifacts if x.get("id") == EXPECTED[run_id]]
        require(len(matches) <= 1, "Duplicate original artifact ID")
        if not matches:
            records.append({
                "run_id": run_id,
                "artifact_id": EXPECTED[run_id],
                "state": "MISSING",
                "days_remaining": None,
            })
            continue
        a = matches[0]
        require(type(a.get("expired")) is bool, "Artifact expired state missing")
        expires = parse_utc(a.get("expires_at"))
        created = parse_utc(a.get("created_at"))
        require(created <= expires <= created + timedelta(days=MAX_GITHUB_PUBLIC_DAYS),
                "Impossible public Actions artifact retention window")
        remaining = (expires - now).total_seconds() / 86400
        available = not a["expired"] and remaining > 0
        records.append({
            "run_id": run_id,
            "artifact_id": a["id"],
            "artifact_name": a.get("name"),
            "expires_at_utc": a["expires_at"],
            "days_remaining": round(max(0.0, remaining), 2),
            "state": ("AVAILABLE_EXPIRING" if available and remaining <= 14
                      else "AVAILABLE_TEMPORARY" if available
                      else "EXPIRED"),
            "content_SHA_verified_by_prior_offline_run_only": True,
            "bytes_archived_indefinitely": False,
        })
    require(seen_runs == set(EXPECTED), "Incomplete source run coverage")
    available_count = sum(x["state"].startswith("AVAILABLE") for x in records)
    soonest = min(
        (x["days_remaining"] for x in records
         if x["days_remaining"] is not None and x["state"].startswith("AVAILABLE")),
        default=None,
    )
    return {
        "phase": "P1_P3_FREE_GITHUB_ORIGINAL_RETENTION_PREFLIGHT",
        "status": (
            "TEMPORARY_ORIGINALS_PRESENT_PERMANENT_REPLAY_BLOCKED"
            if available_count == len(EXPECTED)
            else "ORIGINAL_SOURCE_REPLAY_MISSING_OR_EXPIRED"
        ),
        "as_of_utc": inventory["inspected_at_utc"],
        "original_artifacts_expected": len(EXPECTED),
        "original_artifacts_currently_available": available_count,
        "minimum_remaining_days": soonest,
        "retention_is_permanent": False,
        "license_for_public_vendor_CSV_redistribution_verified": False,
        "public_GitHub_Releases_is_approved_storage": False,
        "Github_Releases_requires_source_data_rights_review": True,
        "source_originals_unavailable_even_before_expiration": list(EXPLICIT_NO_RAW_ORIGINAL),
        "original_source_archive_replay_ready": False,
        "historical_point_in_time_authority_verified": False,
        "fully_replayable_full_market_verified": False,
        "p4_oos_ready": False,
        "source_artifacts": sorted(records, key=lambda x: x["run_id"]),
        "required_next_actions": [
            "DETERMINE_PROVIDER_RAW_DATA_STORAGE_AND_REDISTRIBUTION_RIGHTS",
            "SELECT_LEGAL_NO_COST_DURABLE_OR_USER_PRIVATE_DATA_VAULT",
            "CAPTURE_ORIGINALS_WITH_BYTES_AND_SHA_IN_PERMITTED_STORAGE",
            "INDEPENDENTLY_VERIFY_EXCHANGE_HISTORICAL_PIT_COMPLETENESS",
        ],
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
        "candidate_universe": [],
        "paid_api_calls": 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", required=True)
    p.add_argument("--p1-old", default="reports/p1_pilot_16_source_digests_20261021.json")
    p.add_argument("--p1-new", default="reports/p1_delisted_8_source_digests_20261021.json")
    p.add_argument("--p3-st", default="reports/p3_two_issuer_vendor_st_replay_20261021.json")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    def load(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))
    report = audit(load(args.inventory), load(args.p1_old),
                   load(args.p1_new), load(args.p3_st))
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
