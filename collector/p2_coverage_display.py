"""Keep completeness, computability, and explained non-computability separate."""
import argparse
from collections import Counter
import json
from pathlib import Path


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("coverage counters must be nonnegative integers")
    return value


def _metric(count, total):
    return {"count": count, "total": total, "percent": round(100 * count / total, 2) if total else None}


def summarize(coverage, disposition):
    if (coverage.get("status") != "DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            or coverage.get("trade_gate") != "BLOCKED" or disposition.get("trade_gate") != "BLOCKED"
            or not coverage.get("source_epoch_sha256")
            or coverage["source_epoch_sha256"] != disposition.get("source_epoch_sha256")
            or coverage.get("historical_PIT_verified") is not False
            or disposition.get("historical_PIT_verified") is not False
            or coverage.get("orders") != [] or disposition.get("orders") != []
            or disposition.get("feature_gaps_resolved") != 0):
        raise ValueError("incompatible or unsafe research inputs")
    complete, observed, gap_shards, computed, issuers, gaps, unseen = map(
        _count, (coverage[k] for k in ("feature_complete_shards", "observed_archived_shards",
            "observed_with_feature_gaps_shards", "feature_issuer_count",
            "observed_feature_or_gap_issuers", "issuer_evidence_gap_count", "unobserved_archived_shards")))
    explained = _count(disposition["explained_feature_unavailable"])
    review = _count(disposition["review_required"])
    expected_codes = coverage["gap_issuer_codes"]
    rows = disposition["rows"]
    codes = [row["issuer"] for row in rows]
    reasons = Counter(row["reason"] for row in rows if row["status"] == "EXPLAINED_FEATURE_UNAVAILABLE")
    if (complete + gap_shards != observed or computed + gaps != issuers or explained + review != gaps
            or len(expected_codes) != gaps or len(set(expected_codes)) != gaps
            or len(codes) != gaps or set(codes) != set(expected_codes)
            or sum(reasons.values()) != explained or None in reasons
            or sum(row["status"] == "REVIEW_REQUIRED" for row in rows) != review):
        raise ValueError("coverage counts or gap issuer identities do not reconcile")
    return {
        "source_epoch_sha256": coverage["source_epoch_sha256"], "asof": disposition["asof"],
        "feature_complete_shards": _metric(complete, observed),
        "computed_feature_issuers": _metric(computed, issuers),
        "observed_shards_with_feature_gaps": gap_shards, "unobserved_archived_shards": unseen,
        "explained_uncomputable_issuers": explained, "unexplained_issuers_requiring_review": review,
        "explained_reason_counts": dict(sorted(reasons.items())),
        "feature_gaps_resolved": 0, "historical_PIT_verified": False, "trade_gate": "BLOCKED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("coverage", "disposition", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    a = parser.parse_args()
    result = summarize(json.loads(a.coverage.read_bytes()), json.loads(a.disposition.read_bytes()))
    a.out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
