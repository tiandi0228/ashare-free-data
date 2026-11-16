"""Distinguish frozen feature ineligibility from gaps still needing review."""
import argparse
import json
from pathlib import Path

FIELDS = ("source_shard", "original_csv_sha256", "diagnosis",
          "available_vendor_rows_through_asof", "trailing_vendor_suspended_rows")
REASONS = {
    "FEWER_THAN_21_VENDOR_ROWS_ASOF": "IPO_WINDOW_TOO_SHORT",
    "VENDOR_MARKED_NOT_TRADABLE_AT_ASOF": "HALTED_AT_CUTOFF",
    "VENDOR_SUSPENDED_ROW_WITHIN_LAST_21": "HALT_INTERRUPTS_FEATURE_WINDOW",
}


def compare(replay, pinned):
    if (replay.get("phase") != "P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS"
            or replay.get("status") != "SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY"
            or replay.get("trade_gate") != "BLOCKED" or replay.get("orders") != []
            or replay.get("executable_candidates") != []
            or replay.get("coverage_gaps_resolved") != 0
            or replay.get("historical_PIT_verified") is not False):
        raise ValueError("unexpected gap replay provenance")
    asof = replay["asof_completed_day"]
    epoch = replay["source_epoch_sha256"]
    same_scope = pinned["asof"] == asof and pinned["source_epoch_sha256"] == epoch
    entries = pinned["entries"] if same_scope else {}
    rows = []
    seen = set()
    for r in replay["results"]:
        issuer = r["issuer"]
        if issuer in seen or r.get("asof_date") != asof:
            raise ValueError("duplicate issuer or inconsistent replay cutoff")
        seen.add(issuer)
        evidence = entries.get(issuer)
        matches = (evidence is not None and all(k in evidence and k in r and evidence[k] == r[k]
                                               for k in FIELDS))
        reason = REASONS.get(r["diagnosis"]) if matches else None
        rows.append(dict(issuer=issuer, source_shard=r["source_shard"],
                         status="EXPLAINED_FEATURE_UNAVAILABLE" if reason else "REVIEW_REQUIRED",
                         reason=reason, ordinary_recapture_indicated=False if reason else None))
    if replay.get("research_gap_issuers") != len(rows):
        raise ValueError("replay count mismatch")
    explained = sum(row["reason"] is not None for row in rows)
    return dict(asof=asof, source_epoch_sha256=epoch, pinned_scope_match=same_scope,
                explained_feature_unavailable=explained, review_required=len(rows)-explained,
                feature_gaps_resolved=0, historical_PIT_verified=False, trade_gate="BLOCKED",
                orders=[], executable_candidates=[], rows=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replay", type=Path, required=True)
    p.add_argument("--pinned", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = compare(json.loads(a.replay.read_bytes()), json.loads(a.pinned.read_bytes()))
    with a.out.open("x", encoding="utf-8") as out:
        out.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
