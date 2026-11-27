"""Separate delisting evidence from resumable halt intervals, using pinned originals."""
import argparse,csv,hashlib,io,json,zipfile
from pathlib import Path
from collector.p3_next_originals import safe
from collector.p3_unified_ledger import verified_pdf
from collector.p4_curated_session_exit import sessions_between
CODE="sz.002731"
PENDING="sz.002717"
def sha(b):return hashlib.sha256(b).hexdigest()
def classify(rows,missing,calendar):
    dates=[r["date"] for r in rows]
    if dates!=sorted(set(dates)) or not dates or dates[-1]!="2026-11-12":raise ValueError("unexpected last observation")
    if any(r["code"]!=CODE for r in rows):raise ValueError("wrong issuer")
    expected=[d for d in calendar if d>="2026-11-13"]
    if missing!=expected or len(expected)!=9 or set(dates)&set(expected):raise ValueError("delisting tail mismatch")
    if rows[-1]["tradestatus"]!="1":raise ValueError("last day not active")
    return "DELISTING_TAIL_RETROSPECTIVELY_EXPLAINED"
def run(queue,ledger,bridge,prior,archive,root):
    for r in (queue,ledger,bridge,prior):safe(r)
    if sha(archive.read_bytes())!=queue["source_artifact_sha256"]:raise ValueError("archive mismatch")
    tasks={r["issuer"]:r for r in queue["tasks"]};docs={r["issuer"]:r for r in ledger["records"]};proofs={r["issuer"]:r for r in bridge["records"]}
    if len(tasks)!=19 or set(tasks)!=set(docs) or set(proofs)!={CODE,PENDING}:raise ValueError("wrong scope")
    if prior["counts"]!={"ADDITIONAL_INTERVAL_EVIDENCE_REQUIRED":4,"RETROSPECTIVE_INTERVAL_MATCH":13,"ANNOUNCED_RESUME_AFTER_CUTOFF":2}:raise ValueError("unexpected prior")
    records=[]
    with zipfile.ZipFile(archive) as z:
        for code in (CODE,PENDING):
            t,d,p=tasks[code],docs[code],proofs[code]
            if t["extension_sha256"]!=d["extension_sha256"] or t["extension_sha256"]!=p["extension_sha256"] or d["pdf_sha256"]!=p["original_pdf_sha256"]:raise ValueError("provenance mismatch")
            verified_pdf((root/(code+".pdf")).read_bytes(),d["pdf_sha256"])
            raw=z.read(t["source_member"])
            if sha(raw)!=t["extension_sha256"]:raise ValueError("CSV mismatch")
            rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            if code==CODE:
                if p["status"]!="DELISTED_RETROSPECTIVE":raise ValueError("wrong notice classification")
                status=classify(rows,t["missing_expected_sessions"],sessions_between("2026-10-21",queue["asof"]))
            else:
                if p["status"]!="HALTED_PENDING_DELIST_DECISION" or len(rows)!=26 or any(r["code"]!=code or r["tradestatus"]!="0" for r in rows) or t["missing_expected_sessions"]:raise ValueError("pending decision mismatch")
                status="PENDING_DELIST_DECISION_HALT_OBSERVED"
            records.append(dict(issuer=code,status=status,pdf_sha256=d["pdf_sha256"],extension_sha256=t["extension_sha256"],first_publication_verified=False,full_interval_verified=False,official_certified=False,eligible_for_trading=False,missing_expected_sessions=t["missing_expected_sessions"]))
    return dict(asof=queue["asof"],gap_issuers=19,retrospective_resume_matches=13,announced_resume_after_cutoff=2,delisting_tail_explained=1,pending_delist_halt_observed=1,remaining_other_interval_gaps=2,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","ledger","bridge","prior","archive","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(*[json.loads(x.read_bytes()) for x in (a.queue,a.ledger,a.bridge,a.prior)],a.archive,a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_DELIST_TIMELINE:",json.dumps(r))
