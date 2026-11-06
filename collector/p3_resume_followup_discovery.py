"""Bounded post-halt CNINFO resumption-title research from SHA-replayed originals.

Only a page of index metadata is collected here. An observed '复牌' title
never proves the issuer resumed trading, the historical disclosure timestamp,
or that no other issuer state transitions occurred.
"""
import argparse,json,re
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from collector.p3_real_target_index_probe import query

ISSUER=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
POSITIVE=("复牌","恢复交易","恢复上市")
NEGATIVE=("尚未复牌","未复牌","无法复牌","暂不复牌","不予复牌")
MAX_ISSUERS=3
MAX_QUERY_DAYS=90

def targets(episodes,run_number,today=None,paired=None):
    if (episodes.get("phase")!="P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH"
        or episodes.get("trade_gate")!="BLOCKED" or episodes.get("orders")!=[]
        or episodes.get("historical_PIT_verified") is not False
        or episodes.get("official_PIT_cells_certified")!=0
        or episodes.get("complete_issuer_halt_intervals_certified") is not False):
        raise ValueError("archived episode source not safe")
    todo=episodes.get("official_resumption_followups")
    if (not isinstance(todo,list) or len(todo)!=episodes.get("unpaired_halt_starts_needing_resumption_search")
        or type(run_number)!=int or run_number<1):
        raise ValueError("invalid unpaired official research queue")
    now=today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if not isinstance(now,date):raise ValueError("invalid research day")
    seen=set();ordered=[]
    for row in todo:
        issuer=row.get("issuer");day=row.get("halt_text_date")
        digest=row.get("original_pdf_sha256")
        identifier=str(row.get("halt_announcement_id"))
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or not isinstance(day,str) or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or not identifier.isdigit()
            or row.get("historical_halt_interval_certified") is not False
            or row.get("warning")!="NO_RESUME_IN_BOUNDED_ARCHIVE_IS_NOT_PROOF_OF_CONTINUING_HALT"):
            raise ValueError("untrusted source halt record")
        start=date.fromisoformat(day)
        if start>now:raise ValueError("future source halt candidate")
        key=(issuer,day,identifier)
        if key in seen:raise ValueError("duplicate source followup")
        seen.add(key)
        ordered.append({"issuer":issuer,"source_halt_date":day,
            "source_halt_original_sha256":digest,"source_halt_announcement_id":identifier,
            "source_halt_certified":False})
    ordered.sort(key=lambda r:(r["issuer"],r["source_halt_date"],r["source_halt_announcement_id"]))
    if paired is not None:
        if (not isinstance(paired,dict)
                or paired.get("phase")!="P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS"
                or paired.get("trade_gate")!="BLOCKED"
                or paired.get("historical_PIT_verified") is not False
                or paired.get("official_halt_resume_intervals_certified")!=0
                or paired.get("authenticated_first_publication_count")!=0):
            raise ValueError("invalid prior pairing research evidence")
        unpaired=paired.get("unpaired_original_halt_followups")
        if (not isinstance(unpaired,list)
                or paired.get("unpaired_halt_sources_remaining_in_bounded_research")!=len(unpaired)):
            raise ValueError("invalid prior unpaired count")
        origin={(r["issuer"],r["source_halt_original_sha256"]) for r in ordered}
        needed=set()
        for row in unpaired:
            if not isinstance(row,dict) or row.get("status")!="NO_RESUME_PAIR_IN_LIMITED_ARCHIVE_NOT_PROOF_OF_CONTINUING_HALT":
                raise ValueError("unsafe unpaired status")
            key=(row.get("issuer"),row.get("halt_original_sha256"))
            if key not in origin or key in needed:
                raise ValueError("unpaired evidence not within original halted scope")
            needed.add(key)
        text_pairs=paired.get("text_only_halt_resume_pairs")
        if (not isinstance(text_pairs,list)
                or paired.get("deduplicated_research_text_pairs")!=len(text_pairs)):
            raise ValueError("malformed prior text pairs")
        paired_keys=set()
        for item in text_pairs:
            key=(item.get("issuer"),item.get("halt_original_sha256"))
            if (key not in origin or
                    item.get("historical_first_publication_verified") is not False or
                    item.get("official_resume_effective_date_verified") is not False or
                    item.get("whole_interval_tradability_verified") is not False):
                raise ValueError("unsafe prior research pair")
            paired_keys.add(key)
        if needed != origin-paired_keys:
            raise ValueError("prior pairing coverage does not partition original halts")
        ordered=[r for r in ordered if (r["issuer"],r["source_halt_original_sha256"]) in needed]
    if not ordered:return []
    pages=(len(ordered)+MAX_ISSUERS-1)//MAX_ISSUERS
    page=(run_number-1)%pages
    return ordered[page*MAX_ISSUERS:(page+1)*MAX_ISSUERS]

def window_for_halt(halt,now,cycle):
    """Rotate strictly bounded post-halt date windows, never infer no-resume."""
    if not isinstance(halt,date) or not isinstance(now,date) or halt>now:
        raise ValueError("invalid source dates")
    if type(cycle)!=int or cycle<0:
        raise ValueError("invalid research cycle")
    # Window 0 starts the day before the original halt; all subsequent
    # windows are nonoverlapping, each at most 90 days wide.
    elapsed=(now-halt).days
    total=elapsed//MAX_QUERY_DAYS+1
    segment=cycle%total
    start=halt-timedelta(days=1) if segment==0 else halt+timedelta(days=segment*MAX_QUERY_DAYS)
    end=min(now,halt+timedelta(days=(segment+1)*MAX_QUERY_DAYS-1))
    if end<start or (end-start).days>MAX_QUERY_DAYS:
        raise ValueError("unbounded research window")
    return (start.isoformat(),end.isoformat()),segment,total

def discover(episodes,run_number,client=query,today=None,paired=None):
    now=today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    selected=targets(episodes,run_number,today=now,paired=paired)
    if not selected:
        raise ValueError("no source-backed unpaired historical halt followups")
    source_count=(len(paired["unpaired_original_halt_followups"]) if paired is not None
                  else len(episodes["official_resumption_followups"]))
    source_pages=(source_count+MAX_ISSUERS-1)//MAX_ISSUERS
    cycle=(run_number-1)//source_pages
    results=[];provenance=[]
    for src in selected:
        issuer=src["issuer"]
        halt=date.fromisoformat(src["source_halt_date"])
        window,segment,total=window_for_halt(halt,now,cycle)
        provenance.append({**src,"search_window_start":window[0],
            "search_window_end":window[1],
            "window_segment_index":segment,"window_segment_count":total,
            "research_window_is_exhaustive":False,
            "historical_resume_authenticated":False})
        status="NO_RESUME_TITLE_IN_BOUNDED_INDEX_NOT_NEGATIVE_PROOF"
        candidates=[]
        try:
            found=client(issuer,max_pages=2,research_window=window)
            if not isinstance(found,list) or len(found)>60:
                raise ValueError("invalid official index batch")
            unique=set()
            for notice in found:
                if notice.get("historical_PIT_verified") is not False:
                    raise ValueError("unverified index falsely certified")
                title=notice.get("announcement_title_unverified")
                if not isinstance(title,str) or len(title)>200:
                    raise ValueError("invalid original index title")
                if not any(x in title for x in POSITIVE) or any(x in title for x in NEGATIVE):
                    continue
                identity=notice.get("announcement_id")
                if identity in unique:continue
                unique.add(identity)
                candidates.append(notice)
            candidates.sort(key=lambda r:(r.get("official_pdf_url",""),r["announcement_id"]))
            if candidates:status="RESUMPTION_TITLE_RESEARCH_CANDIDATES_UNVERIFIED"
        except Exception as err:
            status="INDEX_UNAVAILABLE_NOT_NO_RESUMPTION"
            candidates=[]
        results.append({"issuer":issuer,"status":status,
            "candidate_count":len(candidates),
            "source_halt_text_date":src["source_halt_date"],
            "source_halt_original_sha256":src["source_halt_original_sha256"],
            "research_window":list(window),
            "window_segment_index":segment,"window_segment_count":total,
            "candidates":candidates})
    return {"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY",
        "purpose":"BOUNDED_ORIGINAL_PDF_RESUMPTION_FOLLOWUP_RESEARCH",
        "attempted":len(results),
        "source_unpaired_halt_issuer_count":episodes["unpaired_halt_starts_needing_resumption_search"],
        "archive_remaining_unpaired_count":len(paired["unpaired_original_halt_followups"]) if paired is not None else None,
        "previous_text_pairs_are_not_trade_certification":True,
        "window_cycle":cycle,
        "per_issuer_date_window_max_days":MAX_QUERY_DAYS,
        "selected_halt_sources":provenance,
        "max_page_budget_per_issuer":2,
        "results":results,
        "index_exhaustive_or_historical_asof_proof":False,
        "complete_issuer_halt_intervals_certified":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--episodes",required=True)
    p.add_argument("--run-number",required=True,type=int)
    p.add_argument("--out",required=True)
    p.add_argument("--paired",help="SHA-replayed prior original resume pair ledger")
    a=p.parse_args()
    report=discover(
        json.loads(Path(a.episodes).read_text()),a.run_number,
        paired=json.loads(Path(a.paired).read_text()) if a.paired else None)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":report["phase"],"purpose":report["purpose"],
        "attempted":report["attempted"],"source_unpaired_halt_issuer_count":report["source_unpaired_halt_issuer_count"],
        "candidate_count":sum(r["candidate_count"] for r in report["results"]),
        "states":[r["status"] for r in report["results"]],
        "historical_PIT_verified":False,"trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
