"""Generate exact source-bound P3 review packets for dated PDF research clues.

Every candidate remains unverified. A clause match never certifies first
publication, event effective date, trading status, or eligibility.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SHA=re.compile(r"[0-9a-f]{64}\Z")
ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
NOTICE=re.compile(r"[0-9]+\Z")
CLASSES={
    "SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW":"PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW",
    "AMBIGUOUS_MULTIPLE_EVENT_FAMILIES":"QUARANTINE_MULTIPLE_CLAIMS",
    "DATE_CONTEXT_WITHOUT_EXPLICIT_EVENT":"QUARANTINE_NO_EXPLICIT_EVENT",
}


def build(crosswalk,triage):
    if (not isinstance(crosswalk,dict) or not isinstance(triage,dict)
        or crosswalk.get("phase")!="P3_THREE_ASOF_ORIGINAL_NOTICE_DATE_LEAD_CROSSWALK"
        or crosswalk.get("status")!="SHA_BOUND_DATE_TEXT_LEADS_NOT_OFFICIAL_EVENTS"
        or triage.get("phase")!="P3_REAL_P1_DATE_CONTEXT_TRIAGE"
        or crosswalk.get("trade_gate")!="BLOCKED" or triage.get("trade_gate")!="BLOCKED"
        or crosswalk.get("orders")!=[] or triage.get("orders")!=[]
        or crosswalk.get("historical_PIT_verified") is not False
        or triage.get("historical_PIT_verified") is not False
        or crosswalk.get("first_publication_times_independently_authenticated")!=0
        or crosswalk.get("official_state_intervals_certified")!=0
        or triage.get("historical_issuer_states_certified")!=0):
        raise ValueError("unsafe P3 source review")
    leads=crosswalk.get("leads")
    contexts=triage.get("candidate_contexts")
    if (not isinstance(leads,list) or not isinstance(contexts,list)
        or len(leads)>100 or len(leads)!=crosswalk.get("date_context_leads")
        or len(contexts)!=triage.get("research_date_context_count")
        or crosswalk.get("duplicate_source_text_contexts_collapsed",0)!=len(contexts)-len(leads)
        or len(contexts)<len(leads) or crosswalk.get("research_issuers")!=3):
        raise ValueError("P3 clue counts disagree")
    context_by_key={}
    for row in contexts:
        issuer=row.get("issuer") if isinstance(row,dict) else None
        notice=row.get("announcement_id") if isinstance(row,dict) else None
        digest=row.get("original_sha256") if isinstance(row,dict) else None
        day=row.get("date_text") if isinstance(row,dict) else None
        excerpt=row.get("source_text_context") if isinstance(row,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or not isinstance(notice,str) or not NOTICE.fullmatch(notice)
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or not isinstance(day,str) or not isinstance(excerpt,str)
            or not 0<len(excerpt)<=200 or day not in excerpt
            or row.get("historical_effective_date_verified") is not False
            or row.get("historical_publication_time_verified") is not False
            or row.get("human_review_required") is not True):
            raise ValueError("invalid independent source text")
        key=(issuer,notice,digest,day,hashlib.sha256(excerpt.encode()).hexdigest())
        if key in context_by_key:
            # An identical repeated clause is the same source material,
            # never a second independent supporting announcement.
            continue
        context_by_key[key]=excerpt
    result=[]
    used=set()
    for row in leads:
        if not isinstance(row,dict):
            raise ValueError("invalid source-bound event clue")
        issuer=row.get("issuer")
        notice=row.get("announcement_id")
        digest=row.get("original_pdf_sha256")
        day=row.get("source_date_text")
        fingerprint=row.get("source_context_sha256")
        classification=row.get("research_classification")
        directions=row.get("candidate_event_directions")
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or not isinstance(notice,str) or not NOTICE.fullmatch(notice)
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or not isinstance(fingerprint,str) or not SHA.fullmatch(fingerprint)
            or classification not in CLASSES
            or not isinstance(directions,list) or directions!=sorted(set(directions))
            or any(x not in ("HALT_START","RESUME_START","ST_APPLIED",
                             "ST_REMOVED","LISTING_START","DELIST_EFFECTIVE") for x in directions)
            or (classification=="SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW") != (len(directions)==1)
            or (classification=="AMBIGUOUS_MULTIPLE_EVENT_FAMILIES") != (len(directions)>1)
            or row.get("text_is_not_official_first_publication_proof") is not True
            or row.get("historical_first_publication_authenticated") is not False
            or row.get("official_effective_interval_certified") is not False
            or row.get("historical_trade_eligible") is not False):
            raise ValueError("forged candidate event or PIT promotion")
        key=(issuer,notice,digest,day,fingerprint)
        if key in used or key not in context_by_key:
            raise ValueError("unbound or duplicate SHA-matched review lead")
        if (row.get("index_source_scope")=="ARCHIVED_RESEARCH_LEAD_NOT_CURRENT_QUERY"
            and (type(row.get("archived_research_source_run_id")) is not int
                 or row["archived_research_source_run_id"]<=0
                 or row.get("current_index_status")!="INDEX_UNAVAILABLE_NOT_NO_RISK")):
            raise ValueError("archived source lead not independently attributed")
        if (row.get("index_source_scope") not in
            (None,"CURRENT_INDEX_RESEARCH_UNVERIFIED",
             "ARCHIVED_RESEARCH_LEAD_NOT_CURRENT_QUERY")):
            raise ValueError("unknown original index lead provenance")
        used.add(key)
        excerpt=context_by_key[key]
        canonical=json.dumps([issuer,notice,digest,day,fingerprint,directions],
                             ensure_ascii=False,separators=(",",":"))
        result.append({
            "review_id":hashlib.sha256(canonical.encode()).hexdigest()[:20],
            "issuer":issuer,"announcement_id":notice,
            "original_pdf_sha256":digest,
            "original_pdf_url_unverified":row.get("original_pdf_url"),
            "index_source_scope":row.get("index_source_scope","CURRENT_INDEX_RESEARCH_UNVERIFIED"),
            "archived_research_source_run_id":row.get("archived_research_source_run_id"),
            "current_index_status":row.get("current_index_status"),
            "source_date_text_unverified":day,
            "source_context_sha256":fingerprint,
            "source_clause_excerpt":excerpt,
            "event_direction_candidates":"; ".join(directions),
            "review_queue":CLASSES[classification],
            "independent_proofs_needed":"FIRST_PUBLICATION_ORIGINAL_SOURCE; EXCHANGE_EFFECTIVE_STATE_HISTORY; HISTORICAL_ST_ASOF_CROSSCHECK",
            "review_status":"NOT_AUTHENTICATED",
            "independent_first_publication_verified":False,
            "official_effective_interval_verified":False,
            "historical_PIT_verified":False,
            "buy_eligible":False,
        })
    if used!=set(context_by_key):
        raise ValueError("research text clues missing in derived review packet")
    source_class_counts=Counter(CLASSES[row["research_classification"]] for row in leads)
    raw_counts=Counter(row["review_queue"] for row in result)
    if (raw_counts!=source_class_counts or
        Counter(row["research_classification"] for row in leads)!=crosswalk.get("classification_counts")):
        raise ValueError("source event-classification counts diverge")
    # Multiple distinct text fragments describing one logical issuer/notice/
    # day/action are ONE research lead, not independent confirmations.
    # Preserve all fragments but quarantine the entire conflict group.
    logical_counts=Counter(
        (row["issuer"],row["announcement_id"],row["original_pdf_sha256"],
         row["source_date_text_unverified"],row["event_direction_candidates"])
        for row in result
        if row["review_queue"]=="PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW")
    for row in result:
        logical=(row["issuer"],row["announcement_id"],row["original_pdf_sha256"],
                 row["source_date_text_unverified"],row["event_direction_candidates"])
        if (row["review_queue"]=="PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW"
            and logical_counts[logical]>1):
            row["review_queue"]="QUARANTINE_CONFLICTING_TEXT_EXCERPTS"
    ordered=sorted(result,key=lambda r:(r["review_queue"]!="PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW",
                                        r["issuer"],r["announcement_id"],r["source_context_sha256"]))
    counts=Counter(row["review_queue"] for row in ordered)
    return {
        "phase":"P3_ASOF_ORIGINAL_NOTICE_MANUAL_REVIEW_PACKETS",
        "status":"OFFICIAL_PROOF_REQUIRED_NO_PIT_CERTIFICATION",
        "source_epoch_sha256":crosswalk.get("source_epoch_sha256"),
        "total_contexts":len(result),
        "priority_event_candidates":counts["PRIORITY_INDEPENDENT_OFFICIAL_EVENT_REVIEW"],
        "ambiguous_quarantined":counts["QUARANTINE_MULTIPLE_CLAIMS"],
        "conflicting_quarantined":counts["QUARANTINE_CONFLICTING_TEXT_EXCERPTS"],
        "other_quarantined":counts["QUARANTINE_NO_EXPLICIT_EVENT"],
        "review_queue":ordered,
        "official_first_publication_authenticated":0,
        "official_state_intervals_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--crosswalk",type=Path,required=True)
    p.add_argument("--triage",type=Path,required=True)
    p.add_argument("--json-out",type=Path,required=True)
    p.add_argument("--csv-out",type=Path,required=True)
    a=p.parse_args()
    result=build(json.loads(a.crosswalk.read_text()),json.loads(a.triage.read_text()))
    a.json_out.parent.mkdir(parents=True,exist_ok=True)
    a.csv_out.parent.mkdir(parents=True,exist_ok=True)
    a.json_out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    if result["review_queue"]:
        with a.csv_out.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(result["review_queue"][0]))
            writer.writeheader()
            writer.writerows(result["review_queue"])
    print(json.dumps({"total":result["total_contexts"],
        "priority":result["priority_event_candidates"],
        "ambiguous":result["ambiguous_quarantined"],
        "conflicts":result["conflicting_quarantined"],
        "other":result["other_quarantined"],
        "trade_gate":result["trade_gate"]}))


if __name__=="__main__":
    main()
