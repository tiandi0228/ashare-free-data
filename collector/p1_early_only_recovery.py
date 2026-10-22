"""Bounded vendor-early-only delisting-bias RESEARCH sample (not exchange PIT).

Select *up to eight* candidate codes absent from the later vendor roster,
by replaying and hashing actual historical two-date original vendor CSV bytes.
The early/late membership comparison is explicitly hindsight for research
coverage audit, NEVER valid as a backtest entry-day universe.

Raw vendor bars are used only in the ephemeral Runner workspace. This program
writes source digests/status metadata, NOT raw redistributed vendor CSVs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from collector.audit_dated_rosters import audit_archive
from collector.baostock_batch import (
    CAP, END, FIELDS as BAR_FIELDS, START, manifest,
)
from collector.baostock_dated_universe import FIELDS as ROSTER_FIELDS
from collector.audit_delisted_archive import verify_rows

KNOWN_VENDOR_ROSTER_CAPTURE = 39613467121


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def choose_originals(archive, old_manifest, new_manifest):
    """Never select issuer codes from unaudited/unversioned web results."""
    source = audit_archive(archive)
    require(source["status"] == "ORIGINAL_TWO_VENDOR_ROSTERS_REPLAYED_PIT_BLOCKED" and
            source["original_vendor_capture_run"] == KNOWN_VENDOR_ROSTER_CAPTURE and
            source["issuer_pool_size_2025_05_26"] == 3181 and
            source["issuer_pool_size_2026_10_20"] == 3195 and
            source["official_exchange_mainboard_membership_verified"] is False and
            source["trade_gate"] == "BLOCKED",
            "Original two-date vendor issuer list not eligible")
    codes16,_ = manifest(old_manifest)
    codes8,_ = manifest(new_manifest)
    require(len(codes16) == 16 and len(codes8) == 8 and
            len(set(codes16+codes8)) == 24,
            "Known prior 24-issuer history pilot drift")
    with ZipFile(archive) as z:
        def read(day):
            raw = z.read(f"mainboard_prefix_{day}.csv")
            reader = csv.reader(io.StringIO(raw.decode("utf-8")))
            require(tuple(next(reader, ())) == ROSTER_FIELDS,
                    "Vendor roster source columns changed")
            rows = list(reader)
            require(len(rows) in (3181,3195),
                    "Unexpected dated mainboard-prefix count")
            return {r[0] for r in rows}
        early = read("2025-05-26")
        late = read("2026-10-20")
    missing_in_late = early-late
    require(len(missing_in_late) == 32 and
            "sh.600421" in missing_in_late,
            "Source early-only historical issuer cohort drift")
    prior = set(codes16+codes8)
    prospective = sorted(missing_in_late-prior)
    require(len(prospective) >= CAP and
            len(set(prospective)) == len(prospective),
            "Eight distinct not-yet-tested early-only vendor codes unavailable")
    return prospective[:CAP], {
        "source_run_id": KNOWN_VENDOR_ROSTER_CAPTURE,
        "replayed_original_roster_sha": [
            result["full_original_sha256"]
            for result in source["date_results"]
        ],
        "early_only_vendor_issuer_count": 32,
        "early_only_excluding_prior_24_count": len(prospective),
        "selection": "LEXICOGRAPHIC_FIRST_8_EARLY_ONLY_NO_PRIOR_PILOT_CODES",
        "not_a_historical_asof_eligible_universe": True,
        "not_independent_exchange_delisting_proof": True,
    }


def capture(provider, codes, lineage):
    require(type(codes) is list and len(codes) == CAP and
            len(set(codes)) == CAP and
            lineage.get("source_run_id") == KNOWN_VENDOR_ROSTER_CAPTURE and
            lineage.get("not_a_historical_asof_eligible_universe") is True,
            "Frozen vendor early-only research cohort invalid")
    result = {
        "phase": "P1_BOUNDED_VENDOR_EARLY_ONLY_HINDSIGHT_RESEARCH_HISTORY",
        "status": "BLOCKED_PARTIAL",
        "selection_lineage": lineage,
        "issuer_count": CAP,
        "issuer_codes": codes,
        "login_attempts": 1,
        "logical_source_queries": 0,
        "max_logical_source_queries": CAP,
        "results": [],
        "source_raw_bar_bytes_published": False,
        "source_original_bytes_durably_archived": False,
        "vendor_historical_revisions_possible": True,
        "retrospective_selection_uses_future_information": True,
        "valid_for_backtest_membership_asof_early_day": False,
        "official_delisting_state_verified": False,
        "official_historical_PIT_universe_verified": False,
        "paid_api_calls": 0,
        "trade_gate": "BLOCKED",
        "candidate_universe": [],
        "executable_candidates": [],
        "orders": [],
    }
    logged = False
    try:
        auth = provider.login()
        require(getattr(auth, "error_code", None) == "0",
                "Baostock login unavailable")
        logged = True
        for code in codes:
            receipt = {"code": code, "status": "SOURCE_ERROR"}
            result["logical_source_queries"] += 1
            try:
                response = provider.query_history_k_data_plus(
                    code, fields=",".join(BAR_FIELDS),
                    start_date=START, end_date=END,
                    frequency="d", adjustflag="3"
                )
                require(getattr(response, "error_code", None) == "0" and
                        list(response.fields) == BAR_FIELDS,
                        "Expected research bar schema not provided")
                rows = []
                while response.next():
                    require(len(rows) < 600, "Source daily row count over cap")
                    rows.append(response.get_row_data())
                require(rows and all(
                    isinstance(row, (tuple,list)) and
                    len(row) == len(BAR_FIELDS) and
                    all(isinstance(v,str) and "\n" not in v and "," not in v
                        for v in row) for row in rows
                ), "Missing or malformed research bar rows")
                raw = (",".join(BAR_FIELDS)+"\n"+
                       "".join(",".join(row)+"\n" for row in rows)).encode()
                check = verify_rows(code, raw)
                receipt.update({
                    "status": "VENDOR_HISTORY_OBSERVED_NOT_PIT",
                    "original_source_sha256": check["original_csv_sha256"],
                    "original_source_rows": check["source_rows"],
                    "vendor_trade_status_1_rows": check["trade_status_1_rows"],
                    "vendor_trade_status_0_rows": check["trade_status_0_rows"],
                    "first_vendor_row_date": check["first_original_csv_date"],
                    "last_vendor_row_date": check["last_original_csv_date"],
                    "last_vendor_trade_status_1_date": check["last_status_1_date"],
                })
            except Exception as exc:
                receipt["source_error_type"] = type(exc).__name__
            result["results"].append(receipt)
    except Exception as exc:
        result["login_error_type"] = type(exc).__name__
    finally:
        if logged:
            try:provider.logout()
            except Exception:result["logout_error_type"] = "FAILED"
    counts = result["results"]
    result["source_observed_issuers"] = sum(
        r["status"] == "VENDOR_HISTORY_OBSERVED_NOT_PIT" for r in counts)
    result["source_observed_rows"] = sum(
        r.get("original_source_rows", 0) for r in counts)
    if result["source_observed_issuers"] == CAP:
        result["status"] = "EIGHT_HISTORICAL_EARLY_ONLY_VENDOR_SAMPLES_OBSERVED_PIT_BLOCKED"
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artifact", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--pilot16", default="manifests/baostock_pilot.txt")
    p.add_argument("--pilot8", default="manifests/baostock_delisted_8_pilot.txt")
    args = p.parse_args()
    codes, lineage = choose_originals(args.artifact, args.pilot16, args.pilot8)
    import baostock as bs
    report = capture(bs, codes, lineage)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                    encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["status"] ==
        "EIGHT_HISTORICAL_EARLY_ONLY_VENDOR_SAMPLES_OBSERVED_PIT_BLOCKED"
        else 2)


if __name__ == "__main__":
    main()
