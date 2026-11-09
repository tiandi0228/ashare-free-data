"""Research-only source document locator for open P2/P3 gap review tasks.

The SHA of an original PDF and the first time *this collector* archived it
never authenticate the official first-publication instant, historical
exchange state, or an effective halt interval.
"""
import argparse
import json
import re
from datetime import date,datetime,timezone
from pathlib import Path

ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
MAX_EVENTS=10000
MAX_PAIRS=10000


def index(queue,events,pairs):
    if (queue.get("phase")!="P2_P3_SOURCE_SHA_ISSUER_EVIDENCE_REVIEW_QUEUE"
        or queue.get("status")!="UNRESOLVED_OFFICIAL_PROOF_REQUIREMENTS_RESEARCH_ONLY"
        or queue.get("trade_gate")!="BLOCKED"
        or queue.get("historical_PIT_verified") is not False
        or queue.get("feature_gaps_resolved")!=0
        or queue.get("official_halt_intervals_certified")!=0
        or queue.get("orders")!=[] or queue.get("executable_candidates")!=[]
        or events.get("phase")!="P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH"
        or events.get("trade_gate")!="BLOCKED"
        or events.get("historical_PIT_verified") is not False
        or events.get("historical_first_publication_authenticated") is not False
        or events.get("official_PIT_cells_certified")!=0
        or events.get("orders")!=[]
        or pairs.get("phase")!="P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS"
        or pairs.get("trade_gate")!="BLOCKED"
        or pairs.get("historical_PIT_verified") is not False
        or pairs.get("authenticated_first_publication_count")!=0
        or pairs.get("official_halt_resume_intervals_certified")!=0
        or pairs.get("orders")!=[]):
        raise ValueError("unsafe official-original research join")
    epoch=queue.get("source_epoch_sha256")
    tasks=queue.get("tasks")
    text=events.get("research_text_event_claims")
    matched=pairs.get("text_only_halt_resume_pairs")
    if (not isinstance(epoch,str) or not SHA.fullmatch(epoch)
        or not isinstance(tasks,list) or not 1<=len(tasks)<=1000
        or queue.get("gap_issuer_count")!=len(tasks)
        or queue.get("unresolved_issuer_count")!=len(tasks)
        or not isinstance(text,list) or len(text)>MAX_EVENTS
        or not isinstance(matched,list) or len(matched)>MAX_PAIRS
        or events.get("deduplicated_text_event_claims")!=len(text)
        or pairs.get("deduplicated_research_text_pairs")!=len(matched)):
        raise ValueError("unbounded/mismatched official original sources")
    task_by_issuer={}
    for task in tasks:
        issuer=task.get("issuer") if isinstance(task,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in task_by_issuer
            or task.get("source_epoch_sha256")!=epoch
            or task.get("historical_PIT_verified") is not False
            or task.get("feature_gap_resolved") is not False
            or task.get("official_evidence_authenticated") is not False
            or task.get("buy_eligible") is not False):
            raise ValueError("forged research task or duplicate issuer")
        task_by_issuer[issuer]=task
    doc_by_issuer={issuer:[] for issuer in task_by_issuer}
    seen=set()
    for item in text:
        issuer=item.get("issuer") if isinstance(item,dict) else None
        direction=item.get("textual_direction") if isinstance(item,dict) else None
        if direction not in ("HALT_START","RESUME_START"):
            continue
        digest=item.get("original_pdf_sha256")
        day=item.get("claimed_event_day")
        notice=item.get("announcement_id")
        archived=item.get("original_first_archived_research_capture_at_utc")
        path=item.get("original_sha_verified_archive_path")
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or not isinstance(day,str) or not isinstance(notice,str)
            or not notice or not isinstance(archived,str)
            or not isinstance(path,str)
            or item.get("first_publication_authenticated") is not False
            or item.get("effective_date_certified") is not False
            or item.get("historical_asof_trade_eligible") is not False
            or item.get("research_capture_not_official_first_publication") is not True):
            raise ValueError("untrusted historical event text")
        d=date.fromisoformat(day)
        at=datetime.fromisoformat(archived.replace("Z","+00:00"))
        if at.tzinfo is None:
            raise ValueError("naive research capture timestamp")
        if not path.endswith("/"+digest+".pdf"):
            raise ValueError("PDF path does not bind original digest")
        key=(issuer,notice,digest,direction,day)
        if key in seen:
            raise ValueError("duplicate original event claim")
        seen.add(key)
        if issuer not in doc_by_issuer:
            continue
        doc_by_issuer[issuer].append({
            "issuer":issuer,"announcement_id":notice,
            "original_pdf_sha256":digest,
            "original_sha_verified_archive_path":path,
            "claimed_event_text_date":d.isoformat(),
            "textual_direction":direction,
            "first_research_capture_at_utc":at.astimezone(timezone.utc).isoformat(),
            "collection_time_is_not_first_publication":True,
            "historical_first_publication_authenticated":False,
            "effective_date_certified":False,
            "source_text_is_not_official_interval_proof":True,
        })
    pairs_by_issuer={issuer:[] for issuer in task_by_issuer}
    seen_pairs=set()
    for pair in matched:
        issuer=pair.get("issuer") if isinstance(pair,dict) else None
        start=pair.get("halt_original_sha256") if isinstance(pair,dict) else None
        resume=pair.get("resume_original_sha256") if isinstance(pair,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or not isinstance(start,str) or not SHA.fullmatch(start)
            or not isinstance(resume,str) or not SHA.fullmatch(resume)
            or pair.get("historical_first_publication_verified") is not False
            or pair.get("official_resume_effective_date_verified") is not False
            or pair.get("whole_interval_tradability_verified") is not False):
            raise ValueError("forged archived original resumption pair")
        begin=date.fromisoformat(pair["halt_text_date"])
        end=date.fromisoformat(pair["resume_text_date"])
        if end<begin:
            raise ValueError("backward original halt/resume text")
        key=(issuer,start,resume,begin,end)
        if key in seen_pairs:
            raise ValueError("duplicated archived text pair")
        seen_pairs.add(key)
        if issuer not in pairs_by_issuer:
            continue
        pairs_by_issuer[issuer].append({
            "issuer":issuer,
            "halt_original_sha256":start,
            "resume_original_sha256":resume,
            "halt_text_date":begin.isoformat(),
            "resume_text_date":end.isoformat(),
            "official_first_publication_verified":False,
            "continuous_exchange_halt_interval_certified":False,
        })
    result=[]
    for issuer in sorted(task_by_issuer):
        task=task_by_issuer[issuer]
        docs=sorted(doc_by_issuer[issuer],key=lambda d:(
            d["claimed_event_text_date"],d["announcement_id"],d["textual_direction"]))
        items=sorted(pairs_by_issuer[issuer],key=lambda p:(
            p["halt_text_date"],p["resume_text_date"],p["halt_original_sha256"]))
        leads=len(docs)
        pair_count=len(items)
        if (leads!=task.get("official_pdf_halt_resume_text_leads")
            or pair_count!=task.get("research_text_resume_pairs")):
            raise ValueError("task counts diverge from SHA-indexed original sources")
        result.append({
            "issuer":issuer,
            "source_epoch_sha256":epoch,
            "vendor_csv_sha256":task["original_vendor_csv_sha256"],
            "research_action":task["research_action"],
            "original_halt_resume_text_documents":docs,
            "original_resume_research_text_pairs":items,
            "official_first_publication_verified":False,
            "complete_official_state_interval_certified":False,
            "feature_gap_resolved":False,"buy_eligible":False,
        })
    return {
        "phase":"P3_GAP_ISSUER_ORIGINAL_PDF_PROVENANCE_REVIEW_INDEX",
        "status":"SHA_SOURCE_LOCATORS_ONLY_NO_FIRST_PUBLICATION_PROOF",
        "source_epoch_sha256":epoch,
        "gap_issuer_count":len(result),
        "issuer_with_original_halt_resume_text":sum(bool(r["original_halt_resume_text_documents"]) for r in result),
        "issuer_with_resume_text_pair":sum(bool(r["original_resume_research_text_pairs"]) for r in result),
        "total_source_document_text_leads":sum(len(r["original_halt_resume_text_documents"]) for r in result),
        "total_sha_linked_resume_text_pairs":sum(len(r["original_resume_research_text_pairs"]) for r in result),
        "issuers":result,
        "authenticated_first_publication_count":0,
        "certified_exchange_intervals":0,
        "feature_gaps_resolved":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    for field in ("queue","events","pairs","out"):
        p.add_argument("--"+field,type=Path,required=True)
    args=p.parse_args()
    out=index(json.loads(args.queue.read_text()),json.loads(args.events.read_text()),
              json.loads(args.pairs.read_text()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:out[k] for k in (
        "phase","status","gap_issuer_count","issuer_with_original_halt_resume_text",
        "issuer_with_resume_text_pair","total_source_document_text_leads",
        "authenticated_first_publication_count","trade_gate")},ensure_ascii=False))


if __name__=="__main__":
    main()
