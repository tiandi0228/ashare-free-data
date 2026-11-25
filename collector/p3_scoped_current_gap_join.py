"""Join pinned scoped source replays to current production gap evidence without certifying PIT."""
import argparse
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{64}")
EXPECTED = {"sh.600825","sz.002860","sz.002813","sh.605303","sz.002870","sh.603400","sh.601238"}
ARCHIVE = "7028eb4c9cc7f23add64958bc6f2611565476538"
EXTRA = {"sz.000582":"9928ba76ceaeac72506a3e6d4af63bac8d98c279","sz.000668":"7129bdd738de2030c2bd40cb5fa05c1d654fbd8d"}
EXPECTED.update(EXTRA)

def normalize(report):
    issuer=report["issuer"]
    if issuer not in EXTRA: return report
    safe(report)
    if report.get("phase")!="P3_BOUNDED_OFFICIAL_TEXT_VENDOR_STATUS_MATCH" or report.get("first_publication_time_verified") is not False or report.get("full_halt_interval_certified") is not False or report.get("p2_feature_gaps_resolved")!=0:
        raise ValueError("unsafe extra replay")
    archive=report.get("archive_commit",report.get("vendor_archive_commit"))
    if archive!=EXTRA[issuer]: raise ValueError("wrong extra archive")
    if issuer=="sz.000582":
        originals=report["official_originals"]
        if set(originals)!={"halt","resume"}: raise ValueError("missing pair")
        hashes=[digest(x["sha256"]) for x in originals.values()]
    else:
        if report.get("official_pdf_digests_match_pinned_originals") is not True: raise ValueError("unverified pair")
        originals=report["notice_originals"]
        if {x["announcement_number"] for x in originals}!={"2026-064","2026-066"}: raise ValueError("missing pair")
        hashes=[digest(x["observed_pdf_sha256"]) for x in originals]
    if len(hashes)!=2 or len(set(hashes))!=2: raise ValueError("invalid pair")
    return dict(report,archive_commit=archive,entire_issuer_gap_closed=False,notices=[dict(sha256=h,official_first_release=None) for h in hashes])

def digest(x):
    if not isinstance(x,str) or not SHA.fullmatch(x):
        raise ValueError("invalid digest")
    return x

def safe(row):
    if row.get("trade_gate")!="BLOCKED" or row.get("orders")!=[] or row.get("executable_candidates")!=[] or row.get("historical_PIT_verified") is not False:
        raise ValueError("unsafe research evidence")

def partial_calendar_match(index, report):
    safe(report)
    if (report.get("issuer")!="sh.603183" or report.get("archive_commit")!=ARCHIVE
        or report.get("status")!="VENDOR_ROWS_MATCH_RESEARCH_INTERVAL_ORIGINAL_NOTICES_PENDING"
        or report.get("outcome_counts")!={"MATCH":3,"SCHEDULED_CLOSURE":7}
        or report.get("issuer_halt_notice_authenticated") is not False
        or report.get("announcement_available_before_open_verified") is not False
        or report.get("p2_gap_closed") is not False):
        raise ValueError("unsafe partial calendar evidence")
    candidates=report["notice_candidates"]
    if (len(candidates)!=2 or {c["announcement"] for c in candidates}!={"2026-021","2026-022"}
        or any(c.get("original_pdf_verified") is not False or c.get("original_pdf_sha256") is not None for c in candidates)):
        raise ValueError("unsupported partial notice proof")
    csv=digest(report["vendor_csv_sha256"])
    rows=[r for r in index["issuers"] if r["issuer"]=="sh.603183"]
    matched=len(rows)==1 and rows[0]["vendor_csv_sha256"]==csv
    return dict(issuer="sh.603183",source_csv_matches=matched,matched_vendor_days=3 if matched else 0,scheduled_closure_days=7 if matched else 0,original_pdf_verified=False,official_first_release_verified=False,feature_gap_resolved=False,buy_eligible=False)

def join(index,reports,partial=None):
    safe(index)
    if index.get("phase")!="P3_GAP_ISSUER_ORIGINAL_PDF_PROVENANCE_REVIEW_INDEX" or index.get("authenticated_first_publication_count")!=0 or index.get("certified_exchange_intervals")!=0 or index.get("feature_gaps_resolved")!=0:
        raise ValueError("unsafe index")
    epoch=digest(index["source_epoch_sha256"])
    rows=index["issuers"]
    if len(rows)!=index["gap_issuer_count"] or len({r["issuer"] for r in rows})!=len(rows):
        raise ValueError("invalid gap roster")
    scoped={}
    for report in reports:
        report=normalize(report)
        safe(report)
        issuer=report["issuer"]
        if issuer in scoped or issuer not in EXPECTED or report.get("archive_commit")!=EXTRA.get(issuer,ARCHIVE) or report.get("entire_issuer_gap_closed") is not False:
            raise ValueError("invalid replay scope")
        csv=digest(report.get("vendor_csv_sha256",report.get("csv_sha256")))
        hashes=set()
        for n in report["notices"]:
            if not (("official_first_release" in n and n["official_first_release"] is None) or ("first_publication_timestamp_verified" in n and n["first_publication_timestamp_verified"] is False)):
                raise ValueError("unsupported clock proof")
            h=digest(n.get("sha256",n.get("original_sha256")))
            if h in hashes: raise ValueError("duplicate notice")
            hashes.add(h)
        scoped[issuer]=(csv,hashes)
    if set(scoped)!=EXPECTED: raise ValueError("incomplete pinned replay set")
    out=[]
    for row in rows:
        issuer=row["issuer"]
        if row.get("source_epoch_sha256")!=epoch or row.get("buy_eligible") is not False or row.get("feature_gap_resolved") is not False or row.get("official_first_publication_verified") is not False or row.get("complete_official_state_interval_certified") is not False:
            raise ValueError("unsafe issuer evidence")
        csv=digest(row["vendor_csv_sha256"])
        documents={digest(d["original_pdf_sha256"]) for d in row["original_halt_resume_text_documents"] if d["issuer"]==issuer}
        if any(d["issuer"]!=issuer for d in row["original_halt_resume_text_documents"]): raise ValueError("cross issuer notice")
        pairs=[(digest(p["halt_original_sha256"]),digest(p["resume_original_sha256"])) for p in row["original_resume_research_text_pairs"] if p["issuer"]==issuer]
        if len(pairs)!=len(row["original_resume_research_text_pairs"]): raise ValueError("cross issuer pair")
        match=issuer in scoped and scoped[issuer][0]==csv
        hashes=scoped[issuer][1] if match else set()
        exact=sorted(documents & hashes)
        paired=sum(a in hashes and b in hashes for a,b in pairs)
        out.append(dict(issuer=issuer,source_csv_matches=match,matched_notice_sha256=exact,matched_pair_count=paired,official_first_release_verified=False,feature_gap_resolved=False,buy_eligible=False))
    partial_result=partial_calendar_match(index,partial) if partial is not None else None
    return dict(partial_calendar_replay=partial_result,partial_calendar_csv_matches=int(bool(partial_result and partial_result["source_csv_matches"])),phase="P3_SCOPED_REPLAY_CURRENT_GAP_JOIN",source_epoch_sha256=epoch,source_crosswalk_run=45540676282,p2_source_run_id=index["p2_source_run_id"],p3_source_run_id=index["p3_source_run_id"],gap_issuer_count=len(out),issuer_csv_matches=sum(r["source_csv_matches"] for r in out),issuer_notice_matches=sum(bool(r["matched_notice_sha256"]) for r in out),matched_notice_hashes=sum(len(r["matched_notice_sha256"]) for r in out),issuer_pair_matches=sum(r["matched_pair_count"]>0 for r in out),matched_pairs=sum(r["matched_pair_count"] for r in out),issuers=out,official_first_release_count=0,feature_gaps_resolved=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,required=True)
    p.add_argument("--partial-calendar",type=Path)
    p.add_argument("reports",nargs="+",type=Path)
    a=p.parse_args()
    print(json.dumps(join(json.loads(a.index.read_text()),[json.loads(x.read_text()) for x in a.reports],json.loads(a.partial_calendar.read_text()) if a.partial_calendar else None),indent=2))
