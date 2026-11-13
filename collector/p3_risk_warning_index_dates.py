"""Verify bounded CNINFO index metadata without granting publication-time proof."""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

CHINA = timezone(timedelta(hours=8))
CASES = {
    "600363": ("1225584110", "2026-09-29", "2026-09-30"),
    "603517": ("1225609996", "2026-10-19", "2026-10-20"),
    "603838": ("1225608268", "2026-10-17", "2026-10-20"),
}


def verify_index(records):
    if not isinstance(records, list) or len(records) != len(CASES):
        raise ValueError("expected exactly three index records")
    seen = set()
    out = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid index record")
        code = row.get("secCode")
        if not isinstance(code, str) or code not in CASES or code in seen:
            raise ValueError("unknown or duplicate issuer")
        seen.add(code)
        aid, indexed, effective = CASES[code]
        ts = row.get("announcementTime")
        if (row.get("announcementId") != aid
                or row.get("adjunctUrl") != f"finalpage/{indexed}/{aid}.PDF"
                or type(ts) is not int or not 0 < ts < 4102444800000):
            raise ValueError("index notice identity or timestamp mismatch")
        stamp = datetime.fromtimestamp(ts / 1000, CHINA)
        if stamp.date().isoformat() != indexed:
            raise ValueError("index date mismatch")
        out.append({
            "issuer": code, "announcement_id": aid, "index_date": indexed,
            "index_value_china_not_publication_proof": stamp.isoformat(),
            "index_time_is_midnight": stamp.hour == stamp.minute == stamp.second == stamp.microsecond == 0,
            "effective_day_in_notice": effective,
            "first_publication_time_verified": False,
            "historical_non_st_eligibility_verified": False,
        })
    return {"cases": sorted(out, key=lambda row: row["issuer"]),
            "precision_for_acceptance": "INDEX_DATE_ONLY",
            "historical_PIT_verified": False, "trade_gate": "BLOCKED",
            "orders": [], "executable_candidates": []}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("records", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_index(json.loads(args.records.read_text())), indent=2))
