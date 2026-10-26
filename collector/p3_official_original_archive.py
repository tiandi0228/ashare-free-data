"""Append-only free Git storage of real P3 PDF originals and provenance.

This makes retrieved bytes re-checkable beyond ephemeral Actions artifacts.
It DOES NOT authenticate CNINFO historical first-publication times, issuer
state intervals, or trading eligibility. No orders, no approved backtest.
"""
import argparse,hashlib,json,os,re,subprocess,shutil,tempfile
from datetime import datetime,date,time,timedelta,timezone
from pathlib import Path
from urllib.parse import urlparse

BRANCH="research-official-originals-archive"
ISSUER=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}\Z")
DIGEST=re.compile(r"[0-9a-f]{64}\Z")
NOTICE=re.compile(r"[0-9]{5,24}\Z")
PDF_URL=re.compile(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/([0-9]+)\.PDF\Z",re.I)
MAX_TOTAL_PDF_BYTES=12000000

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def safe_id(value):
    if type(value) is not int or value<=0:
        raise ValueError("run ID must be a positive integer")
    return str(value)

def git(*args,cwd=None,check=True):
    return subprocess.run(["git",*args],cwd=cwd,check=check,text=True,capture_output=True)

def prepare(*,originals_root,review,queue,index,run_id,upstream_run_id):
    run_id=safe_id(run_id)
    upstream_run_id=safe_id(upstream_run_id)
    if (review.get("phase")!="P3_P1_ORIGINAL_EFFECTIVE_CLAUSE_REVIEW"
        or queue.get("phase")!="P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST"
        or index.get("phase")!="P3_REAL_P1_LIVE_INDEX_DISCOVERY"
        or review.get("official_PIT_cells_certified")!=0
        or review.get("certified_effective_dates")!=0
        or review.get("authenticated_first_publication_times")!=0
        or review.get("historical_PIT_verified") is not False
        or queue.get("historical_PIT_verified") is not False
        or index.get("historical_PIT_verified") is not False):
        raise ValueError("unsafe official-history source stage")
    if any(x.get("trade_gate")!="BLOCKED" or x.get("orders")!=[] for x in (review,queue,index)):
        raise ValueError("research-only gate missing")
    root=Path(originals_root)
    receipts=read(root/"quality.json")
    if (receipts.get("phase")!="P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE"
        or receipts.get("historical_PIT_verified") is not False
        or receipts.get("historical_first_publication_authenticated") is not False
        or receipts.get("trade_gate")!="BLOCKED"
        or receipts.get("orders")!=[]):
        raise ValueError("invalid original PDF receipts")
    sources=receipts.get("sources")
    if not isinstance(sources,list) or not 0<=len(sources)<=3:
        raise ValueError("bounded original source receipts required")
    index_map={}
    for row in index.get("results",[]):
        issuer=row.get("issuer")
        if not isinstance(issuer,str) or not ISSUER.fullmatch(issuer):
            raise ValueError("invalid issuer index")
        for notice in row.get("candidates",[]):
            key=(issuer,str(notice.get("announcement_id")))
            if key in index_map:continue
            index_map[key]=notice
    evidence={}
    files={}
    total_bytes=0
    for row in sources:
        issuer=row.get("issuer");num=str(row.get("announcement_id"))
        if not isinstance(issuer,str) or not ISSUER.fullmatch(issuer) or not NOTICE.fullmatch(num):
            raise ValueError("invalid source issuer or announcement ID")
        key=(issuer,num)
        if key in evidence:raise ValueError("duplicate original receipt")
        index_original=index_map.get(key)
        if index_original is None:raise ValueError("original not traceable to CNINFO index")
        url=row.get("url")
        match=PDF_URL.fullmatch(url if isinstance(url,str) else "")
        if not match or match.group(1)!=num or url!=index_original.get("official_pdf_url"):
            raise ValueError("untrusted or mismatched source URL")
        retrieved=row.get("original_bytes_verified") is True
        proof={"issuer":issuer,"announcement_id":num,"official_pdf_url":url,
               "title_from_index_unverified":index_original.get("announcement_title_unverified"),
               "index_publication_milliseconds_unverified":index_original.get("index_published_milliseconds_unverified"),
               "historical_first_publication_authenticated":False,
               "effective_date_authenticated":False,"historical_PIT_verified":False,
               "original_retrieved":retrieved}
        if retrieved:
            if row.get("historical_first_publication_authenticated") is not False:
                raise ValueError("incorrect original publication certification")
            filename=f"{issuer.replace('.','_')}_{num}.pdf"
            if row.get("original_file")!=filename:
                raise ValueError("unsafe original filename")
            raw=(root/filename).read_bytes()
            total_bytes+=len(raw)
            digest=row.get("sha256")
            if (not DIGEST.fullmatch(digest or "")
                or not 3000<=len(raw)<=4000000
                or not raw.startswith(b"%PDF-")
                or digest!=sha(raw)):
                raise ValueError("original bytes SHA mismatch")
            observed=datetime.fromisoformat(row.get("observed_at_utc",""))
            if observed.tzinfo is None or observed.utcoffset() is None:
                raise ValueError("missing original capture UTC timezone")
            destination=f"pdf/{issuer.replace('.','_')}/{num}/{digest}.pdf"
            files[destination]=raw
            proof.update({"pdf_sha256":digest,"bytes":len(raw),
                          "archive_path":destination,
                          "captured_at_utc":observed.astimezone(timezone.utc).isoformat()})
        else:
            proof["missing_original_is_not_no_risk"]=True
        evidence[key]=proof
    if total_bytes>MAX_TOTAL_PDF_BYTES or sum(x["original_retrieved"] for x in evidence.values())!=receipts.get("retrieved"):
        raise ValueError("unbounded or inconsistent source bytes")
    tasks={}
    for row in queue.get("official_evidence_tasks",[]):
        key=(row.get("issuer"),row.get("decision_day"),row.get("status_kind"))
        if key in tasks:raise ValueError("duplicate decision source")
        tasks[key]=row
    clauses=[];seen=set()
    reviews=review.get("manual_review_only")
    if not isinstance(reviews,list) or len(reviews)!=review.get("evaluated_research_links") or len(reviews)>3000:
        raise ValueError("invalid original review count")
    for item in reviews:
        key=(item.get("issuer"),str(item.get("announcement_id")))
        ref=evidence.get(key)
        if ref is None or not ref["original_retrieved"] or item.get("original_pdf_sha256")!=ref.get("pdf_sha256"):
            raise ValueError("review without the identical original PDF bytes")
        decision=(item.get("issuer"),item.get("decision_day"),item.get("candidate_kind"))
        task=tasks.get(decision)
        if task is None or task.get("historical_asof_verified") is not False:
            raise ValueError("unmatched historical P1 task")
        vendor_digest=task.get("vendor_csv_sha256")
        if not isinstance(vendor_digest,str) or not DIGEST.fullmatch(vendor_digest):
            raise ValueError("missing archived P1 source SHA")
        identity=(key,decision,item.get("source_date_text"))
        if identity in seen:raise ValueError("duplicate archived clause")
        seen.add(identity)
        if any(item.get(flag) is not False for flag in
               ("historical_asof_usable","historical_first_publication_authenticated",
                "historical_effective_date_authenticated",
                "complete_issuer_state_history_certified")):
            raise ValueError("unsupported trade eligible or effective date claim")
        # Index epoch millis can only be a research hint. Timezone conversion
        # cannot upgrade mutable API metadata into an authenticated PIT timestamp.
        raw_ms=ref["index_publication_milliseconds_unverified"]
        time_class="INDEX_PUBLICATION_TIME_MISSING_UNVERIFIED"
        index_iso=None
        if type(raw_ms) is int and 1000000000000<=raw_ms<=2100000000000:
            claimed=datetime.fromtimestamp(raw_ms/1000,timezone.utc)
            index_iso=claimed.isoformat()
            decision_close=datetime.combine(date.fromisoformat(decision[1]),time(15),tzinfo=timezone(timedelta(hours=8)))
            time_class=("INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED" if claimed>decision_close
                        else "INDEX_TIME_NOT_AFTER_DECISION_CLOSE_UNVERIFIED")
        clauses.append({"issuer":key[0],"announcement_id":key[1],
                        "decision_day":decision[1],"event_kind":decision[2],
                        "source_date_text":item.get("source_date_text"),
                        "local_textual_direction_candidate":item.get("local_textual_direction_candidate"),
                        "source_clause_excerpt":item.get("clause_excerpt"),
                        "original_pdf_sha256":ref["pdf_sha256"],
                        "vendor_csv_sha256":vendor_digest,
                        "source_shard":task.get("source_shard"),
                        "vendor_tradestatus_observed":task.get("vendor_tradestatus_observed"),
                        "claimed_index_publication_utc_unverified":index_iso,
                        "index_time_screen":time_class,
                        "effective_date_authenticated":False,
                        "first_publication_authenticated":False,
                        "decision_time_available_certified":False})
    manifest={"phase":"P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE",
              "run_id":int(run_id),"p1_upstream_run_id":int(upstream_run_id),
              "source_roster_sha256":queue.get("roster_source_sha256"),
              "audited_issuer_count":queue.get("completed_issuers_replayed"),
              "required_official_PIT_cells":queue.get("required_official_evidence_cells"),
              "original_pdf_count":receipts["retrieved"],
              "source_pdf_receipts":[evidence[k] for k in sorted(evidence)],
              "research_date_action_links":clauses,
              "explicit_local_textual_candidate_count":review["explicit_original_clause_candidates"],
              "certified_first_publication_count":0,
              "certified_event_effective_day_count":0,
              "certified_historical_decision_state_count":0,
              "historical_PIT_verified":False,
              "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    if sum(bool(c["local_textual_direction_candidate"]) for c in clauses)!=manifest["explicit_local_textual_candidate_count"]:
        raise ValueError("semantic candidate count mismatch")
    return manifest,files

def persist(manifest,files,repo,namespace="runs"):
    if namespace not in ("runs","resume_runs"):raise ValueError("unsupported immutable evidence namespace")
    if not isinstance(repo,str) or not re.fullmatch(r"[\w.-]+/[\w.-]+",repo):
        raise ValueError("invalid repository")
    run_id=safe_id(manifest["run_id"])
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)/"archive"
        git("clone","--no-checkout",f"https://github.com/{repo}.git",str(work))
        git("config","user.name","github-actions[bot]",cwd=work)
        git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=work)
        exists=git("ls-remote","--heads","origin",BRANCH,cwd=work).stdout.strip()
        if exists:
            git("fetch","origin",BRANCH,cwd=work)
            git("checkout","-B",BRANCH,"FETCH_HEAD",cwd=work)
        else:
            git("checkout","--orphan",BRANCH,cwd=work)
            for p in work.iterdir():
                if p.name==".git":continue
                if p.is_dir():shutil.rmtree(p)
                else:p.unlink()
        expected=(json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
        report=work/namespace/(run_id+".json")
        report.parent.mkdir(parents=True,exist_ok=True)
        if report.exists() and report.read_bytes()!=expected:
            raise ValueError("refuse to rewrite immutable run proof")
        report.write_bytes(expected)
        for name,raw in files.items():
            destination=work/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists() and destination.read_bytes()!=raw:
                raise ValueError("refuse to overwrite immutable official original")
            destination.write_bytes(raw)
        git("add",".",cwd=work)
        if git("diff","--cached","--quiet",cwd=work,check=False).returncode==0:
            return {"new_commit":False,"branch":BRANCH}
        git("commit","-m",f"data(p3): original PDF SHA and PIT-blocked research {run_id}",cwd=work)
        git("push","origin",f"HEAD:refs/heads/{BRANCH}",cwd=work)
        return {"new_commit":True,"branch":BRANCH}

def verify_archive(root,run_id,source_root=None):
    manifest_path=Path(root)/"runs"/(safe_id(run_id)+".json")
    manifest=read(manifest_path)
    if (manifest.get("phase")!="P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE"
        or manifest.get("run_id")!=run_id
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("historical_PIT_verified") is not False
        or manifest.get("orders")!=[]
        or any(manifest.get(k)!=0 for k in ("certified_first_publication_count",
             "certified_event_effective_day_count","certified_historical_decision_state_count"))):
        raise ValueError("invalid archived research-only manifest")
    stored=0;total=0
    for receipt in manifest["source_pdf_receipts"]:
        if not receipt.get("original_retrieved"):continue
        rel=receipt["archive_path"]
        digest=receipt["pdf_sha256"]
        if (not DIGEST.fullmatch(digest) or
            rel!=f"pdf/{receipt['issuer'].replace('.','_')}/{receipt['announcement_id']}/{digest}.pdf"):
            raise ValueError("untrusted archive path")
        data=(Path(root)/rel).read_bytes()
        if len(data)!=receipt["bytes"] or sha(data)!=digest:
            raise ValueError("persisted original PDF corrupted")
        if source_root is not None:
            name=f"{receipt['issuer'].replace('.','_')}_{receipt['announcement_id']}.pdf"
            if (Path(source_root)/name).read_bytes()!=data:
                raise ValueError("archive differs from the live source receipt")
        stored+=1;total+=len(data)
    if stored!=manifest["original_pdf_count"] or total>MAX_TOTAL_PDF_BYTES:
        raise ValueError("incomplete archive")
    return {"phase":"P3_PERSISTED_ORIGINAL_SHA_REPLAY",
            "run_id":run_id,"retrieved_and_persisted_originals":stored,
            "archived_semantic_research_links":len(manifest["research_date_action_links"]),
            "independent_first_publication_verified":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",required=True,choices=["archive","verify"])
    ap.add_argument("--root")
    ap.add_argument("--review");ap.add_argument("--queue")
    ap.add_argument("--index");ap.add_argument("--run-id",type=int,required=True)
    ap.add_argument("--upstream-run-id",type=int)
    ap.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--source-root")
    args=ap.parse_args()
    if args.mode=="archive":
        if args.upstream_run_id is None:raise ValueError("P1 source run ID missing")
        manifest,files=prepare(originals_root=args.source_root,review=read(args.review),
            queue=read(args.queue),index=read(args.index),run_id=args.run_id,
            upstream_run_id=args.upstream_run_id)
        status=persist(manifest,files,args.repo)
        print(json.dumps({"phase":"P3_PERSISTED_ORIGINAL_PDF_ARCHIVE_WRITE",
            "run_id":args.run_id,"stored_pdf_count":manifest["original_pdf_count"],
            "clauses":len(manifest["research_date_action_links"]),
            "archival_branch":status["branch"],"trade_gate":"BLOCKED"}))
    else:
        print(json.dumps(verify_archive(args.root,args.run_id,args.source_root)))
if __name__=="__main__":main()
