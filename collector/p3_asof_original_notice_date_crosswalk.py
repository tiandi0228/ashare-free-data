"""Join three real nontradable-asof issuer PDF text leads to exact original notices.

Every lead is *research only*: a date phrase in a PDF is not proof that the
announcement was public on that day, nor an exchange-effective halt interval.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from collector.p3_original_effective_clause_review import classify

ISSUER = re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
DATE = re.compile(r"20\d{2}年\s*\d{1,2}月\s*\d{1,2}日\Z")
KINDS = ("halt", "st", "listing", "delisting")


def join(discovery, receipt, pdf, triage):
    phases = (
        (discovery, "P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH"),
        (receipt, "P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE"),
        (pdf, "P3_REAL_P1_PDF_TEXT_RESEARCH_CUES"),
        (triage, "P3_REAL_P1_DATE_CONTEXT_TRIAGE"),
    )
    if any(not isinstance(item, dict) or item.get("phase") != phase
           or item.get("trade_gate") != "BLOCKED"
           or item.get("historical_PIT_verified") is not False
           or item.get("orders") != [] for item, phase in phases):
        raise ValueError("unsafe or unrecognized P3 source")
    targets = discovery.get("results")
    sources = receipt.get("sources")
    texts = pdf.get("sources")
    cues = triage.get("candidate_contexts")
    if (not isinstance(targets, list) or len(targets) != 3
        or discovery.get("research_issuers") != 3
        or not isinstance(sources, list) or len(sources) > 3
        or not isinstance(texts, list) or len(texts) != len(sources)
        or pdf.get("source_count") != len(sources)
        or not isinstance(cues, list) or len(cues) > 100
        or triage.get("research_date_context_count") != len(cues)
        or receipt.get("attempted") != len(sources)
        or receipt.get("retrieved") != sum(s.get("original_bytes_verified") is True for s in sources)):
        raise ValueError("unreconciled bounded P3 source count")
    by_target = {}
    by_announcement = {}
    for row in targets:
        issuer = row.get("issuer") if isinstance(row, dict) else None
        if (not isinstance(issuer, str) or not ISSUER.fullmatch(issuer)
            or issuer in by_target
            or row.get("official_asof_state_authenticated") is not False
            or row.get("independent_exchange_status_authenticated") is not False
            or not isinstance(row.get("candidates"), list)):
            raise ValueError("invalid vendor asof issuer")
        by_target[issuer] = row
        for item in row["candidates"]:
            key = (issuer, item.get("announcement_id"))
            if (key in by_announcement or item.get("historical_PIT_verified") is not False
                or item.get("original_bytes_captured") is not False):
                raise ValueError("duplicate or promoted research index notice")
            by_announcement[key] = item
    by_source = {}
    for row in sources:
        key = (row.get("issuer"), row.get("announcement_id"))
        if key in by_source or key[0] not in by_target or key not in by_announcement:
            raise ValueError("original PDF not bound to indexed issuer notice")
        if row.get("historical_first_publication_authenticated") is not False or row.get("historical_PIT_verified") is not False:
            raise ValueError("false original PDF publication certification")
        if row.get("original_bytes_verified") is True:
            digest = row.get("sha256")
            if not isinstance(digest, str) or not SHA.fullmatch(digest):
                raise ValueError("missing independently SHA-verified original")
            if row.get("url") != by_announcement[key].get("official_pdf_url"):
                raise ValueError("original PDF URL diverges from index")
        by_source[key] = row
    by_pdf = {}
    for row in texts:
        key = (row.get("issuer"), row.get("announcement_id"))
        if key in by_pdf or key not in by_source or row.get("historical_PIT_verified") is not False:
            raise ValueError("PDF text not source-bound")
        source = by_source[key]
        if row.get("original_sha256") != source.get("sha256"):
            raise ValueError("PDF text digest not source-bound")
        by_pdf[key] = row
    if set(by_pdf) != set(by_source):
        raise ValueError("PDF text/source count mismatch")

    leads = []
    seen = set()
    for cue in cues:
        key = (cue.get("issuer"), cue.get("announcement_id"))
        src = by_source.get(key)
        text = by_pdf.get(key)
        if (src is None or text is None or src.get("original_bytes_verified") is not True
            or cue.get("original_sha256") != src.get("sha256")
            or text.get("text_status") != "TEXT_EXTRACTED_RESEARCH_ONLY"
            or cue.get("historical_publication_time_verified") is not False
            or cue.get("historical_effective_date_verified") is not False
            or cue.get("human_review_required") is not True):
            raise ValueError("unbound or falsely authenticated PDF date cue")
        day = cue.get("date_text")
        phrase = cue.get("source_text_context")
        if (not isinstance(day, str) or not DATE.fullmatch(day)
            or not isinstance(phrase, str) or not 0 < len(phrase) <= 200
            or day not in phrase):
            raise ValueError("malformed original PDF date context")
        fingerprint = hashlib.sha256(phrase.encode()).hexdigest()
        identity = (*key, src["sha256"], day, fingerprint)
        if identity in seen:
            raise ValueError("duplicated original date context")
        seen.add(identity)
        outcomes = [classify(phrase, day, kind) for kind in KINDS]
        positives = sorted(set(o["local_textual_direction_candidate"] for o in outcomes
                               if o["local_textual_direction_candidate"]))
        classification = ("SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW"
                          if len(positives) == 1 else
                          "AMBIGUOUS_MULTIPLE_EVENT_FAMILIES"
                          if len(positives) > 1 else "DATE_CONTEXT_WITHOUT_EXPLICIT_EVENT")
        notice = by_announcement[key]
        leads.append({
            "issuer":key[0],
            "announcement_id":key[1],
            "original_pdf_sha256":src["sha256"],
            "original_pdf_url":src["url"],
            "index_timestamp_unverified":notice.get("index_published_milliseconds_unverified"),
            "source_date_text":day,
            "source_context_sha256":fingerprint,
            "candidate_event_directions":positives,
            "research_classification":classification,
            "text_is_not_official_first_publication_proof":True,
            "historical_first_publication_authenticated":False,
            "official_effective_interval_certified":False,
            "historical_trade_eligible":False,
        })
    if set(by_target) != {r["issuer"] for r in targets}:
        raise ValueError("missing original research issuer")
    leads.sort(key=lambda r:(r["issuer"],r["announcement_id"],r["source_date_text"],r["source_context_sha256"]))
    return {
        "phase":"P3_THREE_ASOF_ORIGINAL_NOTICE_DATE_LEAD_CROSSWALK",
        "status":"SHA_BOUND_DATE_TEXT_LEADS_NOT_OFFICIAL_EVENTS",
        "source_epoch_sha256":discovery["source_epoch_sha256"],
        "research_issuers":3,
        "sha_verified_original_pdfs":receipt["retrieved"],
        "date_context_leads":len(leads),
        "classification_counts":dict(sorted(Counter(r["research_classification"] for r in leads).items())),
        "leads":leads,
        "first_publication_times_independently_authenticated":0,
        "official_state_intervals_certified":0,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    for arg in ("discovery","receipt","pdf-text","triage","out"):
        p.add_argument("--"+arg,required=True,type=Path)
    a=p.parse_args()
    result=join(json.loads(a.discovery.read_text()),
                json.loads(a.receipt.read_text()),
                json.loads(a.pdf_text.read_text()),
                json.loads(a.triage.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"date_context_leads":result["date_context_leads"],
                      "classification_counts":result["classification_counts"],
                      "first_publication_times_independently_authenticated":0,
                      "official_state_intervals_certified":0,"trade_gate":"BLOCKED"}))

if __name__=="__main__":
    main()
