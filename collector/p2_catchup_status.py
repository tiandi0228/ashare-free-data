"""Read-only diagnostics for P2 coverage lag against a validated P1 archive."""
from collector.p1_checkpoint import validate


def inspect(coverage, checkpoint, archive_status):
    validate(checkpoint)
    source = checkpoint["source_sha256"]
    if (coverage.get("source_epoch_sha256") != source
            or archive_status.get("source_sha256") != source
            or coverage.get("phase") != "P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
            or coverage.get("status") != "DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            or coverage.get("trade_gate") != "BLOCKED"
            or archive_status.get("trade_gate") != "BLOCKED"
            or coverage.get("historical_PIT_verified") is not False
            or coverage.get("coverage_certified_for_trading") is not False
            or any(coverage.get(k) != [] for k in
                   ("orders", "executable_candidates", "actionable_buy_signals"))):
        raise ValueError("incompatible or unsafe coverage snapshot")
    shards = {row["index"]: row["issuer_count"] for row in checkpoint["completed"]}
    archived = archive_status.get("archived_shards")
    if (not isinstance(archived, list) or any(type(n) is not int for n in archived)
            or sorted(archived) != sorted(shards)):
        raise ValueError("P1 archive status and checkpoint disagree")
    known = {f"shard_{i:04d}": issuers for i, issuers in shards.items()}

    def ids(field):
        group = coverage.get(field)
        if (not isinstance(group, list) or any(not isinstance(i, str) or i not in known for i in group)
                or len(set(group)) != len(group)):
            raise ValueError(f"invalid P2 {field}")
        return set(group)

    observed, unobserved = ids("observed_shard_ids"), ids("unobserved_shard_ids")
    gaps = ids("gap_shard_ids")
    old = observed | unobserved
    observed_issuers = sum(known[i] for i in observed)
    expected = {
        "observed_archived_shards": len(observed),
        "observed_with_feature_gaps_shards": len(gaps),
        "feature_complete_shards": len(observed - gaps),
        "unobserved_archived_shards": len(unobserved),
        "archived_original_shards": len(old),
        "observed_feature_or_gap_issuers": observed_issuers,
        "unobserved_issuer_count": sum(known[i] for i in unobserved),
    }
    if (observed & unobserved or not gaps <= observed
            or any(type(coverage.get(k)) is not int or coverage[k] != v for k, v in expected.items())):
        raise ValueError("P2 coverage counts and shard groups disagree")

    pending = sorted(known.keys() - observed)
    return {
        "status": "P2_CATCHUP_PENDING" if pending else "P2_ARCHIVE_OBSERVATION_CAUGHT_UP",
        "source_epoch_sha256": source,
        "p1_archived_shards": len(known),
        "p2_observed_shards": len(observed),
        "pending_shard_ids": pending,
        "pending_issuers": sum(known[i] for i in pending),
        "archived_after_coverage_snapshot_ids": sorted(known.keys() - old),
        "observed_shards_with_feature_gaps": len(gaps),
        "trade_gate": "BLOCKED",
        "historical_PIT_verified": False,
        "orders": [],
    }
