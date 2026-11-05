"""Fail-closed P3 missing-proof queue triage. Never certifies PIT or trades."""
import argparse
import json
from collections import Counter
from pathlib import Path

PHASE = "P3_UNCERTIFIED_PROOF_GAP_TRIAGE"
CATEGORIES = {
    "CONFLICTING_HALTS_MANUAL_REVIEW_FIRST": ("CONFLICT_REQUIRES_ORIGINAL_REVIEW", 0),
    "PAIRED_UNCERTIFIED_HALT_RESUME": ("INDEPENDENT_TIME_AND_INTERVAL_EVIDENCE", 1),
    "UNPAIRED_HALT_NEEDS_RESUME_SOURCE": ("MISSING_RESUMPTION_SOURCE", 2),
    "ORPHAN_RESUMPTION_NEEDS_HALT_SOURCE": ("MISSING_HALT_SOURCE", 3),
}
MAX_ITEMS = 10000


def build(queue):
    if (not isinstance(queue, dict)
            or queue.get("phase") != "P3_ORIGINAL_EVENT_MISSING_PROOF_QUEUE"
            or queue.get("status") != "UNVERIFIED_PIT_WORK_QUEUE_ONLY"
            or queue.get("trade_gate") != "BLOCKED"
            or queue.get("orders") != []
            or queue.get("executable_candidates") != []
            or queue.get("recommendations") != []
            or queue.get("historical_PIT_verified") is not False
            or any(queue.get(k) != 0 for k in (
                "certified_first_publication_count",
                "certified_issuer_state_intervals", "completed_pit_cells",
                "official_first_publication_authenticated_from_capture"))):
        raise ValueError("unsafe or unrecognized P3 proof queue")
    items = queue.get("work_items")
    if (not isinstance(items, list) or len(items) > MAX_ITEMS
            or type(queue.get("work_item_count")) is not int
            or queue["work_item_count"] != len(items)
            or not isinstance(queue.get("work_type_counts"), dict)
            or queue["work_type_counts"] != dict(sorted(
                Counter(x.get("kind") for x in items if isinstance(x, dict)).items()))):
        raise ValueError("incomplete or inconsistent P3 queue")
    rows = []
    for position, item in enumerate(items):
        if (not isinstance(item, dict) or item.get("kind") not in CATEGORIES
                or item.get("historical_PIT_verified") is not False
                or item.get("trade_eligible") is not False
                or not isinstance(item.get("issuer"), str)
                or not isinstance(item.get("missing_independent_proofs"), list)
                or not item["missing_independent_proofs"]
                or len(item["missing_independent_proofs"]) != len(set(
                    str(x) for x in item["missing_independent_proofs"]))
                or any(not isinstance(x, str) or not x for x in item["missing_independent_proofs"])):
            raise ValueError("invalid or falsely certified P3 gap row")
        category, priority = CATEGORIES[item["kind"]]
        if type(item.get("priority")) is not int or item["priority"] != priority:
            raise ValueError("gap priority disagrees with original queue")
        # This is a worklist, not a source of historical exchange state.
        rows.append({
            "queue_index": position,
            "issuer": item["issuer"],
            "source_kind": item["kind"],
            "review_bucket": category,
            "priority": priority,
            "missing_independent_proofs": list(item["missing_independent_proofs"]),
            "official_evidence_status": "NOT_AUTHENTICATED",
            "eligible_for_historical_trade_replay": False,
        })
    counts = Counter(x["review_bucket"] for x in rows)
    if sum(counts.values()) != len(items):
        raise ValueError("gap triage accounting failure")
    return {
        "phase": PHASE,
        "status": "TRIAGED_NOT_CERTIFIED",
        "source_phase": queue["phase"],
        "total_unresolved_work_items": len(rows),
        "review_bucket_counts": dict(sorted(counts.items())),
        "work_items": rows,
        "official_first_publication_authenticated": 0,
        "official_state_intervals_certified": 0,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "recommendations": [],
        "caveat": "TRIAGE_CANNOT_AUTHENTICATE_HISTORICAL_PUBLICATION_OR_EXCHANGE_STATE",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = build(json.loads(Path(args.queue).read_text(encoding="utf-8")))
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in output.items() if k != "work_items"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
