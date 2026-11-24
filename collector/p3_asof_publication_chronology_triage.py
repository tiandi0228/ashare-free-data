"""Read-only chronology triage for CNINFO indexed original event candidates.

The index announcementTime is unverified search metadata, NOT an authenticated
first-publication instant. Claimed effective days in PDF text are likewise
unverified. Comparisons only prioritize independent exchange review.
"""
import argparse
import csv
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

SHA=re.compile(r"[0-9a-f]{64}\Z")
ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
DATE=re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\Z")
PDF_URL=re.compile(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/([0-9]+)\.PDF\Z",re.I)
CLASSES=frozenset(("PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW",
                   "QUARANTINE_MULTIPLE_CLAIMS",
                   "QUARANTINE_CONFLICTING_TEXT_EXCERPTS",
                   "QUARANTINE_NO_EXPLICIT_EVENT"))
SH=ZoneInfo("Asia/Shanghai")


def _day(text):
    m=DATE.fullmatch(text) if isinstance(text,str) else None
    if m is None:
        raise ValueError("invalid original PDF event day phrase")
    try:
        return date(*map(int,m.groups()))
    except ValueError as exc:
        raise ValueError("invalid original PDF event day") from exc


def _index_time(value):
    if value is None:
        return None
    if type(value) is not int or not 946684800000<=value<=4102444800000:
        raise ValueError("malformed/unbounded CNINFO index milliseconds")
    return datetime.fromtimestamp(value/1000,timezone.utc).astimezone(SH)


def triage(packets,crosswalk,discovery):
    if (not isinstance(packets,dict) or not isinstance(crosswalk,dict)
        or not isinstance(discovery,dict)
        or packets.get("phase")!="P3_ASOF_ORIGINAL_NOTICE_MANUAL_REVIEW_PACKETS"
        or packets.get("status")!="OFFICIAL_PROOF_REQUIRED_NO_PIT_CERTIFICATION"
        or crosswalk.get("phase")!="P3_THREE_ASOF_ORIGINAL_NOTICE_DATE_LEAD_CROSSWALK"
        or discovery.get("phase")!="P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH"
        or any(item.get("trade_gate")!="BLOCKED"
               or item.get("historical_PIT_verified") is not False
               or item.get("orders")!=[] for item in (packets,crosswalk,discovery))
        or packets.get("official_first_publication_authenticated")!=0
        or packets.get("official_state_intervals_certified")!=0
        or crosswalk.get("first_publication_times_independently_authenticated")!=0
        or crosswalk.get("official_state_intervals_certified")!=0
        or packets.get("source_epoch_sha256")!=crosswalk.get("source_epoch_sha256")
        or packets.get("source_epoch_sha256")!=discovery.get("source_epoch_sha256")):
        raise ValueError("unsafe cross-source chronology triage")
    rows=packets.get("review_queue")
    leads=crosswalk.get("leads")
    targets=discovery.get("results")
    if (not isinstance(rows,list) or not isinstance(leads,list)
        or not isinstance(targets,list) or len(targets)!=3
        or len(rows)!=packets.get("total_contexts")
        or len(leads)!=crosswalk.get("date_context_leads")
        or len(rows)!=len(leads) or len(rows)>100):
        raise ValueError("unreconciled research source count")
    roster={}
    for item in targets:
        issuer=item.get("issuer") if isinstance(item,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in roster
            or item.get("official_asof_state_authenticated") is not False
            or item.get("independent_exchange_status_authenticated") is not False
            or not isinstance(item.get("original_vendor_csv_sha256"),str)
            or not SHA.fullmatch(item["original_vendor_csv_sha256"])):
            raise ValueError("forged target asof source")
        roster[issuer]=item
    per_lead={}
    for row in leads:
        issuer=row.get("issuer") if isinstance(row,dict) else None
        notice=row.get("announcement_id") if isinstance(row,dict) else None
        sha=row.get("original_pdf_sha256") if isinstance(row,dict) else None
        context=row.get("source_context_sha256") if isinstance(row,dict) else None
        if (issuer not in roster or not isinstance(notice,str) or not notice.isdigit()
            or not isinstance(sha,str) or not SHA.fullmatch(sha)
            or not isinstance(context,str) or not SHA.fullmatch(context)
            or row.get("historical_first_publication_authenticated") is not False
            or row.get("official_effective_interval_certified") is not False
            or row.get("historical_trade_eligible") is not False):
            raise ValueError("untrusted dated PDF event lead")
        key=(issuer,notice,sha,context)
        if key in per_lead:
            raise ValueError("duplicate original notice evidence")
        per_lead[key]=row
    output=[]
    used=set()
    for item in rows:
        issuer=item.get("issuer") if isinstance(item,dict) else None
        notice=item.get("announcement_id") if isinstance(item,dict) else None
        digest=item.get("original_pdf_sha256") if isinstance(item,dict) else None
        fingerprint=item.get("source_context_sha256") if isinstance(item,dict) else None
        key=(issuer,notice,digest,fingerprint)
        lead=per_lead.get(key)
        if (lead is None or key in used or item.get("review_queue") not in CLASSES
            or item.get("review_status")!="NOT_AUTHENTICATED"
            or item.get("independent_first_publication_verified") is not False
            or item.get("official_effective_interval_verified") is not False
            or item.get("historical_PIT_verified") is not False
            or item.get("buy_eligible") is not False
            or item.get("source_date_text_unverified")!=lead.get("source_date_text")
            or item.get("event_direction_candidates")!="; ".join(lead.get("candidate_event_directions",[]))
            or item.get("original_pdf_url_unverified")!=lead.get("original_pdf_url")
            or item.get("index_source_scope")!=lead.get("index_source_scope")):
            raise ValueError("review packet not bound to original notice")
        url=item["original_pdf_url_unverified"]
        match=PDF_URL.fullmatch(url) if isinstance(url,str) else None
        if match is None or match.group(1)!=notice:
            raise ValueError("untrusted original index URL")
        used.add(key)
        event_day=_day(item["source_date_text_unverified"])
        asof=date.fromisoformat(roster[issuer]["vendor_asof_date"])
        index_at=_index_time(lead.get("index_timestamp_unverified"))
        if index_at is None:
            classification="INDEX_TIMESTAMP_ABSENT_UNVERIFIED"
        elif index_at.date()>event_day:
            classification="INDEX_AFTER_EVENT_DAY_REVIEW_REQUIRED"
        elif index_at.date()<event_day:
            classification="INDEX_BEFORE_EVENT_DAY_UNVERIFIED"
        else:
            classification="INDEX_SAME_EVENT_DAY_UNVERIFIED"
        index_after_asof=index_at is not None and index_at.date()>asof
        output.append({
            "review_id":item["review_id"],
            "issuer":issuer,
            "announcement_id":notice,
            "original_pdf_sha256":digest,
            "original_pdf_url":url,
            "source_context_sha256":fingerprint,
            "text_event_day_unverified":event_day.isoformat(),
            "vendor_asof_day_unverified":asof.isoformat(),
            "cninfo_index_time_shanghai_unverified":index_at.isoformat() if index_at else None,
            "index_vs_event_date_research_classification":classification,
            "index_after_vendor_asof_day_research_risk":index_after_asof,
            "index_source_scope":item["index_source_scope"],
            "archived_research_source_run_id":item.get("archived_research_source_run_id"),
            "review_queue":item["review_queue"],
            "first_publication_time_independently_authenticated":False,
            "effective_date_independently_authenticated":False,
            "exchange_state_interval_certified":False,
            "historical_PIT_verified":False,
            "review_status":"NEEDS_INDEPENDENT_OFFICIAL_SOURCE",
            "buy_eligible":False,
        })
    if used!=set(per_lead):
        raise ValueError("unreviewed crosswalk lead")
    return {
        "phase":"P3_ASOF_INDEX_VS_EVENT_CHRONOLOGY_RESEARCH",
        "status":"UNVERIFIED_INDEX_TIMESTAMP_IS_NOT_PUBLICATION_PROOF",
        "source_epoch_sha256":packets["source_epoch_sha256"],
        "reviewed_date_contexts":len(output),
        "priority_review_candidates":sum(r["review_queue"]=="PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW" for r in output),
        "index_after_event_day_research_warnings":sum(r["index_vs_event_date_research_classification"]=="INDEX_AFTER_EVENT_DAY_REVIEW_REQUIRED" for r in output),
        "index_after_vendor_asof_research_warnings":sum(r["index_after_vendor_asof_day_research_risk"] for r in output),
        "review_rows":output,
        "authenticated_first_publication_count":0,
        "certified_exchange_intervals":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    for name in ("packets","crosswalk","discovery","json-out","csv-out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    out=triage(json.loads(a.packets.read_text()),json.loads(a.crosswalk.read_text()),
               json.loads(a.discovery.read_text()))
    a.json_out.parent.mkdir(parents=True,exist_ok=True)
    a.csv_out.parent.mkdir(parents=True,exist_ok=True)
    a.json_out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    if out["review_rows"]:
        with a.csv_out.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(out["review_rows"][0]))
            writer.writeheader()
            writer.writerows(out["review_rows"])
    print(json.dumps({k:out[k] for k in ("reviewed_date_contexts",
        "priority_review_candidates","index_after_event_day_research_warnings",
        "index_after_vendor_asof_research_warnings","trade_gate")}))


if __name__=="__main__":
    main()
