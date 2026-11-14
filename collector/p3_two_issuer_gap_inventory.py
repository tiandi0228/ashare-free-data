"""Read-only rollup of pinned P3 source replays, not a coverage ledger."""
import argparse
import json
from pathlib import Path

EXPECTED = (
    ("sh.600825", 4, 15, "rows", "matched_vendor_days", 349),
    ("sz.002860", 3, 11, "notices", "matched_rows", 350),
    ("sz.002813", 3, 6, "notices", "matched_rows", 353),
    ("sh.605303", 3, 11, "notices", "matched_rows", 354),
)


def inventory(*reports, include_002813=False, include_605303=False):
    expected = EXPECTED if include_605303 else EXPECTED[:3] if include_002813 else EXPECTED[:2]
    if len(reports) != len(expected):
        raise ValueError("wrong report count")
    issuers, hashes = [], set()
    for report, (issuer, count, days, field, day_field, pr) in zip(reports, expected):
        if (report["issuer"] != issuer or report["trade_gate"] != "BLOCKED"
            or report["historical_PIT_verified"] is not False
            or report["entire_issuer_gap_closed"] is not False
            or report["orders"] != [] or report["executable_candidates"] != []):
            raise ValueError("unexpected issuer or unsafe replay")
        matched = report[day_field]
        if isinstance(matched, dict):
            matched = len(matched)
        notices = report[field]
        if type(matched) is not int or matched != days or len(notices) != count:
            raise ValueError("unexpected evidence inventory")
        for notice in notices:
            digest = notice.get("original_sha256", notice.get("sha256"))
            if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest) or digest in hashes):
                raise ValueError("missing or duplicate original hash")
            hashes.add(digest)
            if "official_first_release" not in notice or notice["official_first_release"] is not None:
                raise ValueError("unsupported official first-release proof")
        issuers.append({"issuer": issuer, "source_pr": pr, "verified_notice_originals": count,
                        "matched_vendor_days": days, "official_first_release_verified": 0,
                        "next_gap": "OFFICIAL_FIRST_RELEASE_AND_PREOPEN_VISIBILITY",
                        "entire_issuer_gap_closed": False})
    return {"issuers": issuers, "verified_notice_originals": len(hashes),
            "matched_vendor_issuer_days": sum(row["matched_vendor_days"] for row in issuers),
            "official_first_release_verified": 0, "issuer_gaps_closed": 0,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--include-002813", action="store_true")
    parser.add_argument("--include-605303", action="store_true")
    args = parser.parse_args()
    print(json.dumps(inventory(*(json.loads(p.read_bytes()) for p in args.reports), include_002813=args.include_002813, include_605303=args.include_605303), indent=2))


if __name__ == "__main__":
    main()
