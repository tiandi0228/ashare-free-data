"""Feed pinned notice evidence into the existing point-in-time gate."""
import argparse
import json
from pathlib import Path

from collector.p3_publication_asof_gate import assess

# The progress notice is tested at a checkpoint, not as a new halt.
CASES = {
    "sh.600825": {
        "2026-014": ("halt", "2026-09-07"),
        "2026-018": ("resume", "2026-09-21"),
        "2026-030": ("halt", "2026-10-13"),
        "2026-031": ("resume", "2026-10-16"),
    },
    "sz.002860": {
        "2026-043": ("halt", "2026-09-22"),
        "2026-044": ("progress_checkpoint", "2026-09-30"),
        "2026-047": ("resume", "2026-10-14"),
    },
}


def replay(sh, sz):
    results = []
    for report, issuer, field in ((sh, "sh.600825", "rows"), (sz, "sz.002860", "notices")):
        if (report["issuer"] != issuer or report["trade_gate"] != "BLOCKED"
            or report["orders"] != [] or report["executable_candidates"] != []
            or report["historical_PIT_verified"] is not False):
            raise ValueError("unsafe or mismatched input replay")
        seen = set()
        for row in report[field]:
            number = row.get("announcement_number", row.get("notice_number"))
            if number not in CASES[issuer] or number in seen:
                raise ValueError("unexpected or duplicate notice")
            if "official_first_release" not in row or row["official_first_release"] is not None:
                raise ValueError("unexpected official first-release claim")
            seen.add(number)
            kind, day = CASES[issuer][number]
            # Index clocks deliberately never enter the authenticated timestamp field.
            event = {"issuer": issuer, "kind": kind, "effective_date": day,
                     "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
                     "original_sha256": row.get("original_sha256", row.get("sha256")),
                     "original_bytes_verified": True,
                     "publisher_independently_authenticated": True,
                     "publication_timestamp_independently_authenticated": False,
                     "authenticated_first_published_at": None}
            decision = day + "T09:30:00+08:00"
            result = assess([event], decision)["events"][0]
            results.append({**result, "notice_number": number, "decision_beijing": decision})
        if seen != CASES[issuer].keys():
            raise ValueError("incomplete notice set")
    return {"notice_checks": len(results), "known_at_cutoff": sum(
            r["known_before_decision"] for r in results), "events": results,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs=2)
    args = parser.parse_args()
    print(json.dumps(replay(*(json.loads(p.read_bytes()) for p in args.reports)), indent=2))
