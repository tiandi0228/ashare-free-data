"""Evidence *intake* for P3 official state review, never historical PIT approval.

Accept citation candidates with exact source provenance and chronological sanity,
then park each as UNAUTHENTICATED for an independent review. An HTTPS URL, a
collector capture time, and even a SHA-matched original PDF are NOT proof of
official first-publication time, interval or trading eligibility.
"""
import argparse
import json
import re
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlsplit

SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
ALLOWED_HOSTS = frozenset(("www.sse.com.cn", "www.szse.cn", "www.cninfo.com.cn"))
KINDS = frozenset(("FIRST_PUBLICATION", "HALT_START", "RESUME_START",
                   "ST_APPLIED", "ST_REMOVED", "ASOF_EXCHANGE_TRADING_STATE"))
STATES = frozenset(("TRADABLE", "HALTED", "DELISTED", "UNKNOWN"))
REQUIRED_BASE = frozenset(("SOURCE_AUTHENTIC_ORIGINAL_DOCUMENT_SHA",
                           "INDEPENDENT_FIRST_PUBLICATION_TIME_AND_SOURCE",
                           "EXCHANGE_EFFECTIVE_HALT_RESUME_INTERVAL_OR_LISTING_HISTORY",
                           "COMPLETE_POINT_IN_TIME_TRADABILITY_CROSSCHECK"))


def _instant(value):
    if not isinstance(value,str) or not value or value.endswith("Z") and "T" not in value:
        raise ValueError("invalid official source time")
    try:
        dt = datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid official source time") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("official source timestamp lacks timezone")
    return dt.astimezone(timezone.utc)


def _url(value):
    if not isinstance(value,str) or len(value)>2048:
        raise ValueError("invalid official source URL")
    try:
        u=urlsplit(value)
        port=u.port
    except ValueError as exc:
        raise ValueError("invalid official source URL") from exc
    if (u.scheme!="https" or u.hostname not in ALLOWED_HOSTS
        or u.username is not None or u.password is not None
        or port not in (None,443) or not u.path.startswith("/")
        or not u.path or u.fragment):
        raise ValueError("source is not a direct allowed HTTPS official host")
    return value


def intake(checklist, entries):
    if (not isinstance(checklist,dict)
        or checklist.get("phase")!="P3_MANUAL_OFFICIAL_EVIDENCE_CHECKLIST"
        or checklist.get("trade_gate")!="BLOCKED"
        or checklist.get("historical_PIT_verified") is not False
        or checklist.get("official_first_publication_authenticated")!=0
        or checklist.get("official_state_intervals_certified")!=0
        or checklist.get("feature_gaps_resolved")!=0
        or checklist.get("orders")!=[]
        or not isinstance(entries,list) or len(entries)>1000):
        raise ValueError("unsafe P3 intake source")
    epoch=checklist.get("source_epoch_sha256")
    rows=checklist.get("review_rows")
    if (not isinstance(epoch,str) or not SHA.fullmatch(epoch)
        or not isinstance(rows,list) or not 1<=len(rows)<=400
        or checklist.get("review_count")!=len(rows)):
        raise ValueError("invalid P3 review scope")
    source={}
    for row in rows:
        issuer=row.get("issuer") if isinstance(row,dict) else None
        sha=row.get("vendor_original_csv_sha256") if isinstance(row,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in source or not isinstance(sha,str) or not SHA.fullmatch(sha)
            or row.get("review_status")!="NOT_AUTHENTICATED"
            or row.get("historical_PIT_verified") is not False
            or row.get("buy_eligible") is not False
            or not isinstance(row.get("missing_independent_official_proofs"),str)):
            raise ValueError("invalid reviewed issuer or duplicate")
        source[issuer]=row
    declared_asof=sum(row.get("vendor_gap_diagnosis")==
                      "VENDOR_MARKED_NOT_TRADABLE_AT_ASOF" for row in rows)
    if checklist.get("asof_nontradable_tasks")!=declared_asof:
        raise ValueError("P3 as-of issuer count mismatch")
    if any(row.get("vendor_gap_diagnosis")=="VENDOR_MARKED_NOT_TRADABLE_AT_ASOF"
           and "INDEPENDENT_ASOF_EXCHANGE_TRADING_STATUS" not in
           row["missing_independent_official_proofs"] for row in rows):
        raise ValueError("missing independent as-of exchange proof requirement")

    attached={}
    keyset=set()
    for entry in entries:
        if not isinstance(entry,dict):
            raise ValueError("invalid P3 candidate")
        issuer=entry.get("issuer")
        kind=entry.get("kind")
        digest=entry.get("original_document_sha256")
        vendor_sha=entry.get("vendor_original_csv_sha256")
        day=entry.get("claimed_effective_day")
        if (issuer not in source or kind not in KINDS
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or digest==vendor_sha
            or vendor_sha!=source[issuer]["vendor_original_csv_sha256"]):
            raise ValueError("P3 document candidate not bound to issuer and CSV")
        if kind=="ASOF_EXCHANGE_TRADING_STATE" and source[issuer]["vendor_gap_diagnosis"] != "VENDOR_MARKED_NOT_TRADABLE_AT_ASOF":
            raise ValueError("as-of trading state supplied to unrelated gap")
        try:
            event_day=date.fromisoformat(day)
        except (TypeError,ValueError) as exc:
            raise ValueError("invalid claimed effective date") from exc
        url=_url(entry.get("official_source_url"))
        claimed=_instant(entry.get("claimed_first_publication_at"))
        captured=_instant(entry.get("original_archived_at"))
        if claimed > captured:
            raise ValueError("first publication claim after archived capture")
        if event_day.year<1990 or event_day.year>2100:
            raise ValueError("implausible source event day")
        status=entry.get("claimed_exchange_state")
        if kind=="ASOF_EXCHANGE_TRADING_STATE":
            if status not in STATES:
                raise ValueError("as-of exchange state must be declared")
        elif status is not None:
            raise ValueError("exchange state field only valid for as-of review")
        key=(issuer,kind,day,digest)
        if key in keyset:
            raise ValueError("duplicate official original citation candidate")
        keyset.add(key)
        attached.setdefault(issuer,[]).append({
            "kind":kind,"original_document_sha256":digest,
            "official_source_url":url,
            "claimed_first_publication_at":claimed.isoformat(),
            "claimed_effective_day":event_day.isoformat(),
            "original_archived_at":captured.isoformat(),
            "claimed_exchange_state":status,
            "authenticated_publication":False,
            "authenticated_exchange_effective_date":False,
            "verified_against_original_official_web_record":False,
            "source_citation_only_not_first_publication_proof":True,
        })
    summaries=[]
    for issuer in sorted(source):
        row=source[issuer]
        candidates=sorted(attached.get(issuer,[]),key=lambda x:(
            x["claimed_effective_day"],x["kind"],x["original_document_sha256"]))
        summaries.append({
            "issuer":issuer,
            "vendor_original_csv_sha256":row["vendor_original_csv_sha256"],
            "original_research_text_leads":row["original_pdf_text_leads"],
            "required_official_proofs":row["missing_independent_official_proofs"],
            "candidate_citations":candidates,
            "citations_received":len(candidates),
            "remaining_independent_authentications_required":True,
            "review_status":"NOT_AUTHENTICATED",
            "historical_PIT_verified":False,"buy_eligible":False,
        })
    return {
        "phase":"P3_OFFICIAL_SOURCE_CANDIDATE_INTAKE",
        "status":"UNAUTHENTICATED_CITATIONS_FOR_INDEPENDENT_REVIEW",
        "source_epoch_sha256":epoch,
        "p2_source_run_id":checklist.get("p2_source_run_id"),
        "p3_source_run_id":checklist.get("p3_source_run_id"),
        "issuers_in_scope":len(summaries),
        "asof_nontradable_issuers":declared_asof,
        "candidate_citations_received":len(entries),
        "issuers_with_candidate_citations":sum(bool(x["candidate_citations"]) for x in summaries),
        "review_items":summaries,
        "authenticated_first_publication_count":0,
        "certified_exchange_intervals":0,
        "resolved_p2_feature_gaps":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checklist",required=True,type=Path)
    p.add_argument("--candidates",type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    rows=json.loads(a.candidates.read_text()) if a.candidates else []
    report=intake(json.loads(a.checklist.read_text()),rows)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"issuers_in_scope":report["issuers_in_scope"],
                      "candidate_citations_received":report["candidate_citations_received"],
                      "authenticated_first_publication_count":0,
                      "trade_gate":"BLOCKED"}))


if __name__=="__main__":
    main()
