"""Distinguish frozen feature ineligibility from gaps still needing review."""
import argparse
import json
from collections import Counter
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
        changed = [k for k in FIELDS if evidence is not None and
                   (k not in evidence or k not in r or evidence[k] != r[k])]
        if not same_scope:
            review_code = "PIN_SCOPE_CHANGED"
        elif evidence is None:
            review_code = "NEW_GAP_NOT_IN_PIN"
        elif "original_csv_sha256" in changed:
            review_code = "ORIGINAL_CSV_CHANGED"
        elif changed or r["diagnosis"] not in REASONS:
            review_code = "GAP_METADATA_CHANGED"
        else:
            review_code = None
        reason = REASONS[r["diagnosis"]] if review_code is None else None
        rows.append(dict(issuer=issuer, source_shard=r["source_shard"],
                         status="EXPLAINED_FEATURE_UNAVAILABLE" if reason else "REVIEW_REQUIRED",
                         reason=reason, review_code=review_code, changed_fields=changed,
                         ordinary_recapture_indicated=False if reason else None))
    if replay.get("research_gap_issuers") != len(rows):
        raise ValueError("replay count mismatch")
    explained = sum(row["reason"] is not None for row in rows)
    review_queue = [r for r in rows if r["review_code"] is not None]
    return dict(asof=asof, source_epoch_sha256=epoch, pinned_scope_match=same_scope,
                review_reason_counts=dict(sorted(Counter(r["review_code"] for r in review_queue).items())),
                review_queue=review_queue,
                pinned_issuers_absent_from_current_gap_list=sorted(set(entries)-seen),
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
