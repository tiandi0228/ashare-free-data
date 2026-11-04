"""Prioritized missing-proof work queue from SHA-replayed P3 event text.

This is NOT an exchange state ledger. Even a halt/resume PDF pair cannot
establish first publication, an issuer's actual interval or point-in-time
tradability. The queue names independent evidence still to acquire.
"""
import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

PHASE = "P3_ORIGINAL_EVENT_MISSING_PROOF_QUEUE"
SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")
ACTIONS = {"HALT_START", "RESUME_START", "ST_APPLIED", "ST_REMOVED",
           "LISTING_START", "DELIST_EFFECTIVE"}
MAX_CLAIMS = 10000
MAX_PAIRS = 10000


def _date(raw):
    if not isinstance(raw, str):
        raise ValueError("missing event day")
    value = date.fromisoformat(raw)
    if value.isoformat() != raw:
        raise ValueError("noncanonical event day")
    return value


def _key(issuer, digest, day, action):
    if not isinstance(issuer, str) or not ISSUER.fullmatch(issuer):
        raise ValueError("unverified issuer key")
    if not isinstance(digest, str) or not SHA.fullmatch(digest):
        raise ValueError("missing original PDF SHA")
    _date(day)
    if action not in ACTIONS:
        raise ValueError("unreviewed event direction")
    return issuer, digest, day, action


def _archive_capture_anchor(claim):
    """Location of research capture, NEVER official first publication proof."""
    run_id=claim.get("original_first_archived_research_run_id")
    capture=claim.get("original_first_archived_research_capture_at_utc")
    path=claim.get("original_sha_verified_archive_path")
    issuer=claim.get("issuer")
    notice=claim.get("announcement_id")
    sha=claim.get("original_pdf_sha256")
    if (type(run_id) is not int or run_id<1
            or not isinstance(capture,str)
            or claim.get("research_capture_not_official_first_publication") is not True
            or type(claim.get("original_research_capture_after_claimed_event_text_day"))
                is not bool
            or not isinstance(issuer,str) or not isinstance(notice,str)
            or not isinstance(sha,str)
            or not isinstance(path,str)
            or path!=f"pdf/{issuer.replace('.','_')}/{notice}/{sha}.pdf"):
        raise ValueError("archived research source origin not SHA-linked")
    time=datetime.fromisoformat(capture)
    if time.tzinfo is None or time.utcoffset()!=timezone.utc.utcoffset(time):
        raise ValueError("first capture not UTC source")
    if time.isoformat()!=capture:
        raise ValueError("noncanonical original capture timestamp")
    if (time.date()>_date(claim.get("claimed_event_day"))) != (
            claim["original_research_capture_after_claimed_event_text_day"]):
        raise ValueError("first observed date does not match textual event day")
    return {
        "first_archived_research_capture_utc_not_first_publication":capture,
        "first_archived_original_run_id":run_id,
        "sha_verified_original_archive_path":path,
        "research_capture_after_claimed_text_day":claim[
            "original_research_capture_after_claimed_event_text_day"],
        "official_first_publication_authenticated":False,
    }


def build(source):
    if (not isinstance(source, dict)
            or source.get("phase") != "P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH"
            or source.get("trade_gate") != "BLOCKED"
            or source.get("orders") != []
            or source.get("executable_candidates") != []
            or source.get("historical_PIT_verified") is not False
            or source.get("historical_first_publication_authenticated") is not False
            or source.get("complete_issuer_halt_intervals_certified") is not False
            or source.get("official_PIT_cells_certified") != 0):
        raise ValueError("unsafe P3 original event research source")
    claims, pairs, pending, orphans, overlaps = (
        source.get("research_text_event_claims"),
        source.get("paired_event_texts"),
        source.get("official_resumption_followups"),
        source.get("orphan_resume_texts"),
        source.get("overlap_conflicts"),
    )
    if (not isinstance(claims, list) or len(claims) > MAX_CLAIMS
            or not isinstance(pairs, list) or len(pairs) > MAX_PAIRS
            or not isinstance(pending, list) or len(pending) > MAX_CLAIMS
            or not isinstance(orphans, list) or len(orphans) > MAX_CLAIMS
            or not isinstance(overlaps, list) or len(overlaps) > MAX_CLAIMS
            or any(type(source.get(k)) is not int or source[k] < 0 for k in (
                "runs_replayed", "raw_text_assertion_references",
                "deduplicated_text_event_claims",
                "unpaired_halt_starts_needing_resumption_search",
                "paired_halt_resume_text_claims_unverified",
                "unpaired_resume_claims", "overlapping_halt_claims_without_resume",
                "approval_consent_is_not_effective_date_count"))
            or len(claims) != source["deduplicated_text_event_claims"]
            or len(pairs) != source["paired_halt_resume_text_claims_unverified"]
            or len(pending) != source["unpaired_halt_starts_needing_resumption_search"]
            or len(orphans) != source["unpaired_resume_claims"]
            or len(overlaps) != source["overlapping_halt_claims_without_resume"]
            or source["raw_text_assertion_references"] < len(claims)):
        raise ValueError("truncated or contradictory archived research report")
    known = {}
    approvals = 0
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("untrusted text claim")
        key = _key(claim.get("issuer"), claim.get("original_pdf_sha256"),
                   claim.get("claimed_event_day"), claim.get("textual_direction"))
        if (key in known or claim.get("first_publication_authenticated") is not False
                or claim.get("effective_date_certified") is not False
                or claim.get("historical_asof_trade_eligible") is not False
                or not isinstance(claim.get("announcement_id"), str)
                or not claim["announcement_id"]
                or type(claim.get("approval_not_effective_risk")) is not bool):
            raise ValueError("contradictory source text claim")
        _archive_capture_anchor(claim)
        known[key] = claim
        approvals += int(claim["approval_not_effective_risk"])
    if approvals != source["approval_consent_is_not_effective_date_count"]:
        raise ValueError("approval ambiguity totals inconsistent")
    queue = []
    seen_pairs = set()
    for pair in pairs:
        if (not isinstance(pair, dict)
                or pair.get("status") !=
                "TWO_UNVERIFIED_TEXT_ASSERTIONS_NOT_CONTINUOUS_OFFICIAL_STATE"
                or pair.get("historical_first_publication_authenticated") is not False
                or pair.get("issuer_interval_certified") is not False):
            raise ValueError("pair illegally upgraded to historical issuer state")
        issuer = pair.get("issuer")
        h = _key(issuer, pair.get("halt_pdf_sha256"),
                 pair.get("halt_text_date"), "HALT_START")
        r = _key(issuer, pair.get("resume_pdf_sha256"),
                 pair.get("resume_text_date"), "RESUME_START")
        if h not in known or r not in known or _date(h[2]) > _date(r[2]):
            raise ValueError("pair not anchored to both original text receipts")
        if (h, r) in seen_pairs:
            raise ValueError("duplicate event evidence pair")
        seen_pairs.add((h, r))
        queue.append({
            "priority": 1, "kind": "PAIRED_UNCERTIFIED_HALT_RESUME",
            "issuer": issuer, "halt_pdf_sha256": h[1],
            "resume_pdf_sha256": r[1],
            "halt_text_day_unverified": h[2],
            "resume_text_day_unverified": r[2],
            "halt_announcement_id": known[h]["announcement_id"],
            "resume_announcement_id": known[r]["announcement_id"],
            "halt_original_archive_capture":_archive_capture_anchor(known[h]),
            "resume_original_archive_capture":_archive_capture_anchor(known[r]),
            "approval_or_consent_risk": bool(
                known[h]["approval_not_effective_risk"] or
                known[r]["approval_not_effective_risk"]),
            "missing_independent_proofs": [
                "INDEPENDENT_FIRST_PUBLICATION_TIMESTAMP_FOR_BOTH_ORIGINALS",
                "OFFICIAL_EFFECTIVE_HALT_AND_RESUME_DATES",
                "HISTORICAL_EXCHANGE_STATUS_CONTINUITY",
                "DECISION_TIME_AVAILABILITY_AND_PIT_MEMBERSHIP"],
            "historical_PIT_verified": False, "trade_eligible": False,
        })
    for item in pending:
        if not isinstance(item, dict):
            raise ValueError("unknown unpaired halt item")
        issuer, day, digest = (item.get("issuer"), item.get("halt_text_date"),
                               item.get("original_pdf_sha256"))
        h = _key(issuer, digest, day, "HALT_START")
        if (h not in known or item.get("historical_halt_interval_certified") is not False):
            raise ValueError("unpaired halt not anchored to original")
        queue.append({
            "priority": 2, "kind": "UNPAIRED_HALT_NEEDS_RESUME_SOURCE",
            "issuer": issuer, "halt_pdf_sha256": digest,
            "halt_text_day_unverified": day,
            "halt_announcement_id": known[h]["announcement_id"],
            "halt_original_archive_capture":_archive_capture_anchor(known[h]),
            "missing_independent_proofs": [
                "OFFICIAL_RESUMPTION_OR_NONRESUMPTION_SOURCE",
                "INDEPENDENT_FIRST_PUBLICATION_TIMESTAMP",
                "OFFICIAL_EFFECTIVE_INTERVAL_AND_PIT_MEMBERSHIP"],
            "historical_PIT_verified": False, "trade_eligible": False,
        })
    for item in orphans:
        if not isinstance(item, dict):
            raise ValueError("unknown orphan resumption")
        issuer, day = item.get("issuer"), item.get("resumption_day_text")
        if (not isinstance(issuer, str) or not ISSUER.fullmatch(issuer)):
            raise ValueError("orphan issuer")
        _date(day)
        if not any(k[0] == issuer and k[2] == day and k[3] == "RESUME_START"
                   for k in known):
            raise ValueError("orphan resume not independently text-anchored")
        queue.append({
            "priority": 3, "kind": "ORPHAN_RESUMPTION_NEEDS_HALT_SOURCE",
            "issuer": issuer, "resume_text_day_unverified": day,
            "missing_independent_proofs": [
                "ORIGINAL_HALT_ANNOUNCEMENT_AND_SHA",
                "INDEPENDENT_FIRST_PUBLICATION_TIMESTAMP",
                "OFFICIAL_EFFECTIVE_INTERVAL_AND_PIT_MEMBERSHIP"],
            "historical_PIT_verified": False, "trade_eligible": False,
        })
    for item in overlaps:
        if not isinstance(item, dict) or not isinstance(item.get("issuer"), str):
            raise ValueError("invalid repeated halt overlap")
        issuer = item["issuer"]
        if not ISSUER.fullmatch(issuer):
            raise ValueError("overlap issuer")
        old, new = item.get("previous_announcement"), item.get("next_announcement")
        # The source episode ledger reports announcement IDs only. Rebind
        # EACH conflicting halt to its SHA-pinned original text claim.
        # Multiple HALT_START clauses in one PDF remain ambiguous candidates,
        # not a silently selected or historically certified transition.
        def halt_source_candidates(announcement):
            selected = [
                claim for claim in claims
                if (claim["issuer"] == issuer
                    and claim["announcement_id"] == announcement
                    and claim["textual_direction"] == "HALT_START")
            ]
            if not 1 <= len(selected) <= 20:
                raise ValueError("missing or ambiguous beyond cap halt-source SHA")
            return [
                {
                    "original_pdf_sha256": claim["original_pdf_sha256"],
                    "source_halt_text_day_unverified": claim["claimed_event_day"],
                    "source_announcement_id": claim["announcement_id"],
                    "approval_or_consent_risk": claim[
                        "approval_not_effective_risk"],
                    "independent_first_publication_authenticated": False,
                    "historical_issuer_state_certified": False,
                    "archived_research_original_capture":_archive_capture_anchor(claim),
                } for claim in sorted(selected, key=lambda c: (
                    c["claimed_event_day"], c["original_pdf_sha256"]))
            ]
        if (not isinstance(old, str) or not isinstance(new, str)
                or not old or not new):
            raise ValueError("missing overlapping halt notice identity")
        # Some PDF text extractors emit repeated HALT_START clauses from the
        # SAME announcement. A duplicate clause is not a second legal halt,
        # but it is an unresolved evidence conflict requiring manual review.
        # Preserve the SHA and date(s); never reject the entire archival
        # pipeline or certify a fabricated second independent publication.
        same_announcement = old == new
        preceding = halt_source_candidates(old)
        following = halt_source_candidates(new)
        chronology = all(
            a["source_halt_text_day_unverified"] <=
            b["source_halt_text_day_unverified"]
            for a in preceding for b in following)
        queue.append({
            "priority": 0, "kind": "CONFLICTING_HALTS_MANUAL_REVIEW_FIRST",
            "issuer": issuer, "previous_announcement_id": old,
            "next_announcement_id": new,
            "previous_halt_original_sha_and_text_day_candidates": preceding,
            "next_halt_original_sha_and_text_day_candidates": following,
            "same_announcement_id_reused_in_halt_conflict": same_announcement,
            "separate_original_announcements_authenticated": False,
            "multiple_halt_clauses_need_manual_disambiguation": (
                same_announcement or len(preceding) > 1 or len(following) > 1),
            "text_date_order_unverified_consistent": (
                chronology if not same_announcement else None),
            "independently_verified_official_state_continuity": False,
            "missing_independent_proofs": [
                "SAME_ANNOUNCEMENT_CLAUSE_REPETITION_NOT_TWO_INDEPENDENT_EVENTS",
                "REVIEW_BOTH_SHA_PINNED_ORIGINAL_PDF_CLAUSES_AND_REVISIONS",
                "RESOLVE_OVERLAPPING_OR_REPEATED_HALT_NOTICES",
                "INDEPENDENT_FIRST_PUBLICATION_TIMESTAMP_FOR_BOTH_ORIGINALS",
                "OFFICIAL_STATUS_INTERVAL_AND_PUBLICATION_TIMELINE",
                "DECISION_ASOF_MEMBERSHIP_CANNOT_DEFAULT_TO_TRADEABLE"],
            "historical_PIT_verified": False, "trade_eligible": False,
        })
    queue.sort(key=lambda r: (
        r["priority"], r["issuer"], r.get("halt_text_day_unverified", ""),
        r.get("resume_text_day_unverified", ""),
        r.get("halt_announcement_id", ""), r.get("previous_announcement_id", "")))
    if len(queue) != len(pairs)+len(pending)+len(orphans)+len(overlaps):
        raise ValueError("missing evidence review work items")
    return {
        "phase": PHASE, "status": "UNVERIFIED_PIT_WORK_QUEUE_ONLY",
        "upstream_archived_runs_replayed": source["runs_replayed"],
        "upstream_unique_text_events": len(claims),
        "work_items": queue,
        "work_item_count": len(queue),
        "work_type_counts": dict(sorted(Counter(x["kind"] for x in queue).items())),
        "certified_first_publication_count": 0,
        "certified_issuer_state_intervals": 0,
        "completed_pit_cells": 0, "historical_PIT_verified": False,
        "source_claims_with_sha_verified_archive_capture":len(claims),
        "source_claims_first_archive_capture_after_text_event_day":sum(
            claim["original_research_capture_after_claimed_event_text_day"]
            for claim in claims),
        "official_first_publication_authenticated_from_capture":0,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "recommendations": [],
        "caveat": "TEXTUAL_PAIR_IS_NOT_OFFICIAL_TRADING_STATE_OR_FIRST_PUBLICATION",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    source = json.loads(Path(args.episodes).read_text())
    out = build(source)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k != "work_items"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
