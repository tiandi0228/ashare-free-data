"""Independently reconstruct unverified CNINFO index-vs-decision chronology.

Cross-check each persisted research link against the original official PDF
SHA receipt and its raw mutable-index millisecond value. A matching index
timestamp is NOT historical first-publication authentication, and timestamp
availability is NOT proof of complete issuer status or the ability to trade.
"""
import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

PHASE = "P3_INDEPENDENT_UNVERIFIED_INDEX_CHRONOLOGY_GUARD"
PDF_SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")
NOTICE = re.compile(r"[0-9]{5,24}\Z")
MIN_MS = 1000000000000
MAX_MS = 2100000000000
CN = timezone(timedelta(hours=8))


def _utc(text):
    if not isinstance(text, str):
        raise ValueError("missing timezone-aware original capture")
    point = datetime.fromisoformat(text)
    if point.tzinfo is None or point.utcoffset() is None:
        raise ValueError("naive timestamp is not usable")
    return point.astimezone(timezone.utc)


def _rebuild_index(source, decision):
    raw = source.get("index_publication_milliseconds_unverified")
    if type(raw) is not int or not MIN_MS <= raw <= MAX_MS:
        return None, "INDEX_PUBLICATION_TIME_MISSING_UNVERIFIED"
    claimed = datetime.fromtimestamp(raw / 1000, timezone.utc)
    close = datetime.combine(decision, time(15), tzinfo=CN).astimezone(timezone.utc)
    classification = ("INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED"
                      if claimed > close else
                      "INDEX_TIME_NOT_AFTER_DECISION_CLOSE_UNVERIFIED")
    return claimed, classification


def audit(manifest):
    base = {
        "phase": PHASE, "status": "REJECTED", "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
        "historical_PIT_verified": False, "first_publication_authenticated": False,
        "historical_issuer_state_certified": False, "trade_authorized": False,
    }

    def reject(reason):
        return dict(base, reason=reason)

    try:
        if (not isinstance(manifest, dict)
                or manifest.get("phase") != "P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE"
                or manifest.get("trade_gate") != "BLOCKED"
                or manifest.get("orders") != []
                or manifest.get("executable_candidates") != []
                or manifest.get("historical_PIT_verified") is not False
                or any(manifest.get(k) != 0 for k in (
                    "certified_first_publication_count",
                    "certified_event_effective_day_count",
                    "certified_historical_decision_state_count"))):
            return reject("UNSAFE_ARCHIVED_SOURCE_MANIFEST")
        receipts = manifest.get("source_pdf_receipts")
        links = manifest.get("research_date_action_links")
        if (not isinstance(receipts, list) or len(receipts) > 3
                or not isinstance(links, list) or len(links) > 3000):
            return reject("INVALID_OR_UNBOUNDED_ARCHIVED_INPUT")
        stored = {}
        for source in receipts:
            if not isinstance(source, dict):
                return reject("INVALID_ORIGINAL_RECEIPT")
            issuer, notice, digest = (source.get("issuer"),
                                      source.get("announcement_id"),
                                      source.get("pdf_sha256"))
            if (not isinstance(issuer, str) or not ISSUER.fullmatch(issuer)
                    or not isinstance(notice, str) or not NOTICE.fullmatch(notice)
                    or source.get("historical_PIT_verified") is not False
                    or source.get("historical_first_publication_authenticated") is not False
                    or source.get("effective_date_authenticated") is not False):
                return reject("UNSAFE_ORIGINAL_RECEIPT")
            key = (issuer, notice)
            if key in stored:
                return reject("DUPLICATE_ORIGINAL_RECEIPT")
            if source.get("original_retrieved") is True:
                if not isinstance(digest, str) or not PDF_SHA.fullmatch(digest):
                    return reject("MISSING_ORIGINAL_SHA")
                captured = _utc(source.get("captured_at_utc"))
                stored[key] = (source, captured)
            elif source.get("original_retrieved") is False:
                stored[key] = (source, None)
            else:
                return reject("UNKNOWN_ORIGINAL_RETRIEVAL_STATUS")
        if sum(source["original_retrieved"] for source, _ in stored.values()) != manifest.get("original_pdf_count"):
            return reject("ORIGINAL_RECEIPT_COUNT_MISMATCH")
        counts = Counter()
        per_link = []
        for row in links:
            if not isinstance(row, dict):
                return reject("INVALID_ARCHIVED_LINK")
            key = (row.get("issuer"), str(row.get("announcement_id")))
            if key not in stored:
                return reject("LINK_WITHOUT_ARCHIVED_ORIGINAL")
            source, captured = stored[key]
            if (captured is None
                    or row.get("original_pdf_sha256") != source.get("pdf_sha256")
                    or any(row.get(k) is not False for k in (
                        "effective_date_authenticated",
                        "first_publication_authenticated",
                        "decision_time_available_certified"))):
                return reject("LINK_SOURCE_OR_CERTIFICATION_MISMATCH")
            decision_text = row.get("decision_day")
            if not isinstance(decision_text, str):
                return reject("MISSING_DECISION_DATE")
            decision = date.fromisoformat(decision_text)
            if decision.isoformat() != decision_text:
                return reject("NONCANONICAL_DECISION_DATE")
            point, classification = _rebuild_index(source, decision)
            expected_utc = point.isoformat() if point is not None else None
            if (row.get("index_time_screen") != classification
                    or row.get("claimed_index_publication_utc_unverified") != expected_utc):
                return reject("CONTRADICTORY_INDEX_TIME_OR_DECISION_CLASSIFICATION")
            counts[classification] += 1
            if point is not None and point > captured:
                counts["INDEX_TIME_LATER_THAN_CAPTURE_SUSPECT_METADATA"] += 1
            if captured.date() > decision:
                counts["ORIGINAL_CAPTURE_AFTER_DECISION_DATE"] += 1
            per_link.append({
                "issuer": key[0], "announcement_id": key[1],
                "decision_day": decision.isoformat(),
                "original_pdf_sha256": source["pdf_sha256"],
                "raw_index_time_class_unverified": classification,
                "claimed_index_utc_unverified": expected_utc,
                "first_independent_capture_at_utc": captured.isoformat(),
                "first_publication_authenticated": False,
                "effective_issuer_state_certified": False,
                "historical_asof_usable": False,
                "cautions": [
                    "MUTABLE_INDEX_TIME_NOT_INDEPENDENT_FIRST_PUBLICATION",
                    "CAPTURE_TIME_NOT_HISTORICAL_PUBLICATION_PROOF",
                    "NO_CONTINUOUS_ISSUER_STATE_HISTORY",
                ],
            })
        after = counts["INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED"]
        before = counts["INDEX_TIME_NOT_AFTER_DECISION_CLOSE_UNVERIFIED"]
        missing = counts["INDEX_PUBLICATION_TIME_MISSING_UNVERIFIED"]
        if after + before + missing != len(links):
            return reject("UNRECONCILED_INDEX_SCREEN_TOTALS")
        return dict(base,
            status="INDEX_CHRONOLOGY_CROSSCHECK_RESEARCH_ONLY",
            archived_run_id=manifest.get("run_id"),
            pdf_originals_retrieved=manifest["original_pdf_count"],
            research_links_rechecked=len(links),
            index_after_decision_close_unverified=after,
            index_not_after_decision_close_unverified=before,
            index_time_missing_or_malformed=missing,
            index_later_than_capture_suspect=counts[
                "INDEX_TIME_LATER_THAN_CAPTURE_SUSPECT_METADATA"],
            captured_after_decision_date=counts[
                "ORIGINAL_CAPTURE_AFTER_DECISION_DATE"],
            source_sha_linked_chronology_checks=per_link,
            certified_first_publication_times=0,
            certified_issuer_state_intervals=0,
            limitations=[
                "RECALCULATED_INDEX_TIME_IS_STILL_MUTABLE_METADATA",
                "BEFORE_CLOSE_INDEX_HINT_DOES_NOT_CERTIFY_ASOF_INFORMATION",
                "PDF_CAPTURE_TIME_CANNOT_BACKDATE_HISTORICAL_DISCLOSURE",
                "NO_PIT_ST_HALT_LISTING_OR_CORPORATE_ACTION_CERTIFICATION",
            ],
        )
    except (ValueError, TypeError, KeyError, OSError, OverflowError):
        return reject("SOURCE_OR_TIMESTAMP_NOT_VERIFIABLE")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    try:
        source = json.loads(Path(args.manifest).read_text())
    except (OSError, ValueError, UnicodeError):
        source = None
    result = audit(source)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:result.get(k) for k in (
        "status", "research_links_rechecked",
        "index_after_decision_close_unverified",
        "index_not_after_decision_close_unverified",
        "index_time_missing_or_malformed",
        "index_later_than_capture_suspect",
        "certified_first_publication_times", "trade_gate"
    )}, ensure_ascii=False))
    if result["status"] == "REJECTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
