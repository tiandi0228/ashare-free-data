"""P3 priority-zero conflict original review packet (research only).

No inferred halt interval, issuer tradability or historical first publication.
Produces deterministic review checklist with immutable SHA-linked original
candidates and explicit independent proof requirements.
"""
import argparse,json,re
from pathlib import Path

PHASE="P3_CONFLICT_ORIGINAL_REVIEW_PACKET_UNCERTIFIED"
SHA=re.compile(r"[0-9a-f]{64}\Z")
MAX=1000
REQ=(
    "INDEPENDENT_OFFICIAL_FIRST_PUBLICATION_TIME",
    "INDEPENDENT_EXCHANGE_HALT_EFFECTIVE_SESSION",
    "INDEPENDENT_EXCHANGE_RESUMPTION_OR_EXPLICIT_CONTINUATION",
    "DISTINGUISH_REPEATED_TEXT_CLAUSE_FROM_SEPARATE_NOTICE",
)

def build(triage):
    if (not isinstance(triage,dict)
        or triage.get("phase")!="P3_UNCERTIFIED_PROOF_GAP_TRIAGE"
        or triage.get("status")!="TRIAGED_NOT_CERTIFIED"
        or triage.get("trade_gate")!="BLOCKED"
        or triage.get("orders")!=[] or triage.get("executable_candidates")!=[]
        or triage.get("historical_PIT_verified") is not False
        or triage.get("official_first_publication_authenticated")!=0
        or triage.get("official_state_intervals_certified")!=0):
        raise ValueError("untrusted P3 gap triage")
    items=triage.get("work_items")
    counts=triage.get("review_bucket_counts")
    if (not isinstance(items,list) or len(items)>MAX
        or type(triage.get("total_unresolved_work_items")) is not int
        or len(items)!=triage["total_unresolved_work_items"]
        or not isinstance(counts,dict)
        or sum(counts.values())!=len(items)
        or any(type(n) is not int or n<0 for n in counts.values())):
        raise ValueError("inconsistent P3 queue counts")
    conflict_count=counts.get("CONFLICT_REQUIRES_ORIGINAL_REVIEW",0)
    results=[]
    for pos,item in enumerate(items):
        if not isinstance(item,dict):
            raise ValueError("malformed triage record")
        if item.get("review_bucket")!="CONFLICT_REQUIRES_ORIGINAL_REVIEW":
            continue
        data=item.get("original_research_review_evidence")
        if (item.get("priority")!=0 or
            item.get("source_kind")!="CONFLICTING_HALTS_MANUAL_REVIEW_FIRST" or
            item.get("eligible_for_historical_trade_replay") is not False or
            item.get("official_evidence_status")!="NOT_AUTHENTICATED" or
            not isinstance(data,dict) or
            item.get("queue_index")!=pos or
            not isinstance(item.get("issuer"),str)):
            raise ValueError("invalid priority-zero conflict")
        prev=data.get("previous_halt_original_sha_and_text_day_candidates")
        nxt=data.get("next_halt_original_sha_and_text_day_candidates")
        if not isinstance(prev,list) or not isinstance(nxt,list) or not prev or not nxt:
            raise ValueError("missing conflicting halt originals")
        sources=[]
        for side,entries in (("PREVIOUS",prev),("NEXT",nxt)):
            if len(entries)>20:raise ValueError("unbounded original clauses")
            for e in entries:
                if (not isinstance(e,dict) or
                    not isinstance(e.get("original_pdf_sha256"),str) or
                    not SHA.fullmatch(e["original_pdf_sha256"]) or
                    e.get("independent_first_publication_authenticated") is not False or
                    e.get("historical_issuer_state_certified") is not False):
                    raise ValueError("fake original or certified timing")
                original=e.get("archived_research_original_capture")
                if (not isinstance(original,dict) or
                    original.get("official_first_publication_authenticated") is not False or
                    not isinstance(original.get("sha_verified_original_archive_path"),str) or
                    not original["sha_verified_original_archive_path"].endswith(
                        "/"+e["original_pdf_sha256"]+".pdf")):
                    raise ValueError("missing independent archive SHA anchor")
                sources.append({"side":side,"original_pdf_sha256":e["original_pdf_sha256"],
                    "original_archive_path":original["sha_verified_original_archive_path"],
                    "text_day_unverified":e.get("source_halt_text_day_unverified"),
                    "announcement_id":e.get("source_announcement_id"),
                    "first_publication_authenticated":False})
        results.append({"queue_index":pos,"issuer":item["issuer"],
            "same_announcement_id_reused":data.get("same_announcement_id_reused_in_halt_conflict"),
            "multiple_halt_clauses_need_manual_disambiguation":data.get(
                "multiple_halt_clauses_need_manual_disambiguation"),
            "original_candidates":sources,
            "missing_independent_proofs":list(REQ),
            "historical_halt_interval_certified":False,
            "official_first_publication_authenticated":False,
            "manual_review_required":True})
    if len(results)!=conflict_count:
        raise ValueError("missing priority-zero P3 conflicts")
    return {"phase":PHASE,"status":"REVIEW_PACKETS_ONLY_NO_PIT_CERTIFICATION",
        "source_queue_unresolved_items":len(items),"priority_zero_conflicts":len(results),
        "packets":results,"historical_first_publication_authenticated":0,
        "official_halt_resume_intervals_certified":0,"historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--triage",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    out=build(json.loads(Path(args.triage).read_text()))
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="packets"},ensure_ascii=False))
if __name__=="__main__":
    main()
