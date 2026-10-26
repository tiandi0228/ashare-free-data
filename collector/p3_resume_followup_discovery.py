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

def targets(episodes,run_number,today=None):
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
    if not ordered:return []
    pages=(len(ordered)+MAX_ISSUERS-1)//MAX_ISSUERS
    page=(run_number-1)%pages
    return ordered[page*MAX_ISSUERS:(page+1)*MAX_ISSUERS]

def discover(episodes,run_number,client=query,today=None):
    now=today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    selected=targets(episodes,run_number,today=now)
    if not selected:
        raise ValueError("no source-backed unpaired historical halt followups")
    results=[];provenance=[]
    for src in selected:
        issuer=src["issuer"]
        halt=date.fromisoformat(src["source_halt_date"])
        beginning=halt-timedelta(days=1)
        finish=min(now,halt+timedelta(days=MAX_QUERY_DAYS))
        if finish<beginning:raise ValueError("invalid official followup window")
        window=(beginning.isoformat(),finish.isoformat())
        provenance.append({**src,"search_window_start":window[0],
            "search_window_end":window[1],
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
            "research_window":list(window),"candidates":candidates})
    return {"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY",
        "purpose":"BOUNDED_ORIGINAL_PDF_RESUMPTION_FOLLOWUP_RESEARCH",
        "attempted":len(results),
        "source_unpaired_halt_issuer_count":episodes["unpaired_halt_starts_needing_resumption_search"],
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
    a=p.parse_args()
    report=discover(json.loads(Path(a.episodes).read_text()),a.run_number)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":report["phase"],"purpose":report["purpose"],
        "attempted":report["attempted"],"source_unpaired_halt_issuer_count":report["source_unpaired_halt_issuer_count"],
        "candidate_count":sum(r["candidate_count"] for r in report["results"]),
        "states":[r["status"] for r in report["results"]],
        "historical_PIT_verified":False,"trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
