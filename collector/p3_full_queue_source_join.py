"""Research-only connection of SHA-backed official PDFs to frozen P1 issuer-day tasks.

A captured original and PDF date phrase never prove its first publication,
effective status date, uninterrupted historical status, or decision-day access.
"""
import argparse,json,re
from datetime import date
from pathlib import Path

MAP={"listing":"LISTING_CUE","st":"ST_RISK_CUE",
     "halt":"TRADING_HALT_CUE","delisting":"DELIST_CUE"}
SHA=re.compile(r"[0-9a-f]{64}\Z")
CHINA_DAY=re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\Z")
MAX_RESEARCH_DISTANCE_DAYS=14

def reconcile(queue,scout,index,originals,replay,triage):
    if (queue.get("phase")!="P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST"
        or scout.get("phase")!="P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE"
        or index.get("phase")!="P3_REAL_P1_LIVE_INDEX_DISCOVERY"
        or originals.get("phase")!="P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE"
        or replay.get("phase")!="P3_REAL_P1_ORIGINAL_INDEPENDENT_REPLAY"
        or triage.get("phase")!="P3_REAL_P1_DATE_CONTEXT_TRIAGE"):
        raise ValueError("mismatched research phase")
    for q in (queue,scout,index,originals,replay,triage):
        if q.get("trade_gate")!="BLOCKED" or q.get("orders")!=[]:
            raise ValueError("unsafe research upstream")
    if (queue.get("historical_PIT_verified") is not False
        or scout.get("official_PIT_verified") is not False
        or index.get("historical_PIT_verified") is not False
        or originals.get("historical_PIT_verified") is not False
        or replay.get("historical_first_publication_authenticated") is not False
        or triage.get("historical_PIT_verified") is not False
        or originals.get("retrieved")!=replay.get("independently_sha_verified")):
        raise ValueError("unverified source promoted to PIT or replay mismatch")
    selected=[r["issuer"] for r in scout["targets"]]
    if len(selected)!=len(set(selected)) or index.get("attempted")!=len(selected):
        raise ValueError("scout/index coverage mismatch")
    if [r["issuer"] for r in index["results"]]!=selected:
        raise ValueError("index did not query all selected issuers")
    originals_by_key={}
    for o in originals["sources"]:
        if o.get("issuer") not in selected:raise ValueError("PDF not in selected scope")
        key=(o.get("issuer"),o.get("announcement_id"))
        if key in originals_by_key:raise ValueError("duplicate original")
        if o.get("historical_first_publication_authenticated") is not False:
            raise ValueError("invalid historical publication claim")
        if o.get("original_bytes_verified") is True and not SHA.fullmatch(o.get("sha256","")):
            raise ValueError("missing original SHA")
        originals_by_key[key]=o
    target_cells={(r["issuer"],r["decision_day"],r["status_kind"]):r
                  for r in queue["official_evidence_tasks"] if r["issuer"] in selected}
    if len(target_cells)!=sum(r["issuer"] in selected for r in queue["official_evidence_tasks"]):
        raise ValueError("duplicate historical source issuer-day-kind")
    context_leads=[];seen_leads=set();outside_window=0;duplicates_filtered=0
    for c in triage.get("candidate_contexts",[]):
        if (c.get("issuer") not in selected or
            c.get("historical_effective_date_verified") is not False or
            c.get("historical_publication_time_verified") is not False):
            raise ValueError("bad issuer or temporal promotion")
        key=(c["issuer"],c["announcement_id"])
        original=originals_by_key.get(key)
        if original is None or not original.get("original_bytes_verified"):
            raise ValueError("date context lacks independently replayed PDF original")
        if c.get("original_sha256")!=original.get("sha256"):
            raise ValueError("PDF text cue SHA mismatch")
        phrase=c.get("date_text")
        match=CHINA_DAY.fullmatch(phrase if isinstance(phrase,str) else "")
        if not match:raise ValueError("unparseable PDF date context")
        try:context_date=date(*map(int,match.groups()))
        except ValueError as exc:raise ValueError("invalid PDF date") from exc
        for (issuer,day,kind),cell in sorted(target_cells.items()):
            if issuer!=c["issuer"] or MAP[kind] not in c.get("candidate_event_cues",[]):
                continue
            decision=date.fromisoformat(day)
            days_delta=(context_date-decision).days
            if abs(days_delta)>MAX_RESEARCH_DISTANCE_DAYS:
                outside_window+=1
                continue
            identity=(issuer,day,kind,c["announcement_id"],phrase)
            if identity in seen_leads:
                duplicates_filtered+=1
                continue
            seen_leads.add(identity)
            vendor_nontrading=cell.get("vendor_tradestatus_observed")=="0"
            context_leads.append({"issuer":issuer,"decision_day":day,"kind":kind,
                "announcement_id":c["announcement_id"],
                "pdf_sha256":c["original_sha256"],"date_text":phrase,
                "date_distance_from_decision_days":days_delta,
                "vendor_nontrading_context_match_research_only":bool(kind=="halt" and vendor_nontrading),
                "original_pdf_retrieved_research_only":True,
                "historical_first_publication_utc_authenticated":False,
                "historical_effective_date_authenticated":False,
                "decision_day_trading_state_authenticated":False})
    return {"phase":"P3_FULL_P1_OFFICIAL_SOURCE_SCOUT_RESEARCH",
        "full_source_issuer_count":queue["completed_issuers_replayed"],
        "full_source_required_PIT_cells":queue["required_official_evidence_cells"],
        "scouted_issuers":selected,"index_lookups":len(selected),
        "official_pdf_originals_sha_replayed":replay["independently_sha_verified"],
        "research_issuer_day_date_cue_links":len(context_leads),
        "date_context_heuristic_max_distance_days":MAX_RESEARCH_DISTANCE_DAYS,
        "out_of_window_candidate_pairs_excluded":outside_window,
        "duplicated_candidate_pairs_excluded":duplicates_filtered,
        "vendor_nontrading_date_context_links_research_only":sum(x["vendor_nontrading_context_match_research_only"] for x in context_leads),
        "date_cue_leads":context_leads,
        "official_PIT_cells_certified":0,
        "first_publication_times_independently_authenticated":0,
        "historical_effective_state_transitions_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for name in ("queue","scout","index","originals","replay","triage","out"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    inputs=[json.loads(Path(getattr(a,k)).read_text()) for k in ("queue","scout","index","originals","replay","triage")]
    q=reconcile(*inputs)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in q.items() if k!="date_cue_leads"}))
if __name__=="__main__":main()
