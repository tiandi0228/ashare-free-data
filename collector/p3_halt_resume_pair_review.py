"""Pair SHA-replayed halt and resume text across bounded archival runs.

Pairs are only research leads. Neither PDF title nor dated same-clause text
proves historical first publication or a continuous exchange trading interval.
"""
import argparse,hashlib,json,re
from datetime import date
from pathlib import Path
from collector.p3_resume_original_archive import verify_persisted

DAY=re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")

def review(episodes,root):
    if (episodes.get("phase")!="P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH"
        or episodes.get("trade_gate")!="BLOCKED" or episodes.get("orders")!=[]
        or episodes.get("historical_PIT_verified") is not False
        or episodes.get("official_PIT_cells_certified")!=0
        or episodes.get("complete_issuer_halt_intervals_certified") is not False):
        raise ValueError("unsafe archived halt ledger")
    halts=episodes.get("official_resumption_followups")
    if (not isinstance(halts,list) or
        len(halts)!=episodes.get("unpaired_halt_starts_needing_resumption_search")):
        raise ValueError("missing source halt scope")
    lookup={}
    for item in halts:
        sha=item.get("original_pdf_sha256")
        if not isinstance(sha,str) or not SHA.fullmatch(sha) or item.get("historical_halt_interval_certified") is not False:
            raise ValueError("unauthenticated halt source")
        key=(item.get("issuer"),sha)
        if key in lookup:raise ValueError("duplicate original halt")
        lookup[key]=date.fromisoformat(item["halt_text_date"])
    root=Path(root)
    manifests=sorted((root/"resume_runs").glob("*.json"))
    if not 1<=len(manifests)<=500:raise ValueError("missing or excessive resume archives")
    pairs={};seen_pdfs={};count=0;wrong_order=0;no_text=0
    for path in manifests:
        if not path.stem.isdigit():raise ValueError("wrong archive run id")
        run_id=int(path.stem)
        result=verify_persisted(root,run_id)
        if result["trade_gate"]!="BLOCKED" or result["historical_PIT_verified"] is not False:
            raise ValueError("unsafe resumed source replay")
        manifest=json.loads(path.read_text())
        sources=manifest.get("source_halt_records")
        if not isinstance(sources,list):raise ValueError("invalid original halted scope")
        source_map={r["issuer"]:r for r in sources}
        if len(source_map)!=len(sources):raise ValueError("duplicated halted issuer")
        for row in sources:
            halt=lookup.get((row["issuer"],row["source_halt_original_sha256"]))
            if halt is None or halt.isoformat()!=row["source_halt_date"] or row.get("historical_resume_authenticated") is not False:
                raise ValueError("archived halt SHA not present in verified original episode")
        for row in manifest["resume_notice_source_receipts"]:
            if not row.get("original_pdf_retrieved"):continue
            issuer=row["issuer"]
            src=source_map.get(issuer)
            if (src is None or
                row["source_halt_original_sha256"]!=src["source_halt_original_sha256"] or
                row["source_halt_text_day"]!=src["source_halt_date"]):
                raise ValueError("resume original not associated with same halt SHA")
            original=(issuer,row["announcement_id"])
            digest=row["pdf_sha256"]
            if original in seen_pdfs and seen_pdfs[original]!=digest:
                raise ValueError("same notice id with inconsistent original PDF SHA")
            seen_pdfs[original]=digest
            leads=row.get("resume_same_clause_text_candidates")
            if not isinstance(leads,list):raise ValueError("missing resume text source")
            if not leads:no_text+=1
            for line in leads:
                count+=1
                if count>10000:raise ValueError("unbounded research assertions")
                phrase=line.get("pdf_date_phrase")
                m=DAY.fullmatch(phrase if isinstance(phrase,str) else "")
                if not m:raise ValueError("invalid resumption text date")
                resume=date(*map(int,m.groups()))
                if (line.get("original_sha256")!=digest
                    or line.get("first_publication_authenticated") is not False
                    or line.get("resumption_date_authenticated") is not False
                    or not isinstance(line.get("date_clause_unverified"),str)
                    or phrase not in line["date_clause_unverified"]):
                    raise ValueError("PDF excerpt or publisher timestamp not independently proven")
                halted=lookup[(issuer,digest if False else src["source_halt_original_sha256"])]
                if resume<halted:
                    wrong_order+=1
                    continue
                key=(issuer,src["source_halt_original_sha256"],digest,resume.isoformat())
                if key not in pairs:
                    pairs[key]={"issuer":issuer,
                        "halt_original_sha256":src["source_halt_original_sha256"],
                        "resume_original_sha256":digest,
                        "halt_text_date":halted.isoformat(),
                        "resume_text_date":resume.isoformat(),
                        "resume_announcement_id":row["announcement_id"],
                        "original_resume_pdf_url":row["official_pdf_url"],
                        "source_clause_unverified":line["date_clause_unverified"],
                        "run_ids":set(),
                        "historical_first_publication_verified":False,
                        "official_resume_effective_date_verified":False,
                        "whole_interval_tradability_verified":False}
                pairs[key]["run_ids"].add(run_id)
    result=sorted(pairs.values(),key=lambda r:(r["issuer"],r["halt_text_date"],r["resume_text_date"]))
    for row in result:row["run_ids"]=sorted(row["run_ids"])
    linked={(r["issuer"],r["halt_original_sha256"]) for r in result}
    still=[{"issuer":issuer,"halt_original_sha256":sha,
           "status":"NO_RESUME_PAIR_IN_LIMITED_ARCHIVE_NOT_PROOF_OF_CONTINUING_HALT"}
           for issuer,sha in sorted(lookup) if (issuer,sha) not in linked]
    return {"phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
        "archived_resume_runs_replayed":len(manifests),
        "unique_resume_pdf_originals_replayed":len(seen_pdfs),
        "resume_text_candidates_total":count,
        "deduplicated_research_text_pairs":len(result),
        "resume_text_before_halt_rejected":wrong_order,
        "pdfs_without_exact_resume_text":no_text,
        "unpaired_halt_sources_remaining_in_bounded_research":len(still),
        "text_only_halt_resume_pairs":result,
        "unpaired_original_halt_followups":still,
        "authenticated_first_publication_count":0,
        "official_halt_resume_intervals_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--episodes",required=True);p.add_argument("--archive",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=review(json.loads(Path(a.episodes).read_text()),a.archive)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items()
        if k not in ("text_only_halt_resume_pairs","unpaired_original_halt_followups")},ensure_ascii=False))
if __name__=="__main__":main()
