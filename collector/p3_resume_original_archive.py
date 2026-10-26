"""Persist bounded resume-title original PDFs with exact archived halt SHA lineage.

Original CNINFO index title, issuer PDF text and reference dates are only
research candidates. First publication, actual resume and continuous exchange
trading status are unverified. Never generate orders or unlock any gate.
"""
import argparse,hashlib,json,re
from datetime import datetime,date,timezone
from pathlib import Path
from collector.p3_official_original_archive import persist,verify_archive,BRANCH
from collector.p3_real_p1_pdf_replay import audit as replay_originals
from collector.p3_original_effective_clause_review import classify

SHA=re.compile(r"[0-9a-f]{64}\Z")
URL=re.compile(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/(\d+)\.PDF\Z",re.I)
MAX_PDF_BYTES=12000000

def prepare(index,source_root,text_report,run_id):
    if (type(run_id)!=int or run_id<1
        or index.get("phase")!="P3_REAL_P1_LIVE_INDEX_DISCOVERY"
        or index.get("purpose")!="BOUNDED_ORIGINAL_PDF_RESUMPTION_FOLLOWUP_RESEARCH"
        or index.get("historical_PIT_verified") is not False
        or index.get("complete_issuer_halt_intervals_certified") is not False
        or index.get("trade_gate")!="BLOCKED" or index.get("orders")!=[]
        or text_report.get("phase")!="P3_REAL_P1_PDF_TEXT_RESEARCH_CUES"
        or text_report.get("historical_PIT_verified") is not False
        or text_report.get("trade_gate")!="BLOCKED" or text_report.get("orders")!=[]):
        raise ValueError("unsafe resume original provenance")
    root=Path(source_root)
    replay=replay_originals(root)
    receipt=json.loads((root/"quality.json").read_text())
    if (replay["independently_sha_verified"]!=receipt.get("retrieved")
        or text_report.get("independently_replayed_originals")!=receipt.get("retrieved")
        or text_report.get("source_count")!=receipt.get("attempted")
        or receipt.get("historical_first_publication_authenticated") is not False):
        raise ValueError("independent original and PDF text mismatch")
    sources=index.get("selected_halt_sources")
    if (not isinstance(sources,list) or not 1<=len(sources)<=3
        or index.get("attempted")!=len(sources)
        or len(index.get("results",[]))!=len(sources)):
        raise ValueError("missing original evidence-backed halted issuer scope")
    source_by_issuer={}
    for row in sources:
        issuer=row.get("issuer");digest=row.get("source_halt_original_sha256")
        if (issuer in source_by_issuer or not isinstance(digest,str)
            or not SHA.fullmatch(digest)
            or row.get("source_halt_certified") is not False
            or row.get("historical_resume_authenticated") is not False):
            raise ValueError("invalid prior halt source original SHA or certification")
        date.fromisoformat(row["source_halt_date"])
        source_by_issuer[issuer]=row
    index_candidates={}
    for item in index["results"]:
        issuer=item.get("issuer")
        if issuer not in source_by_issuer:raise ValueError("index has out-of-scope issuer")
        for cand in item["candidates"]:
            key=(issuer,str(cand.get("announcement_id")))
            if key in index_candidates:raise ValueError("duplicate resumption notice index ID")
            match=URL.fullmatch(cand.get("official_pdf_url",""))
            if (not match or match.group(1)!=key[1]
                or cand.get("historical_PIT_verified") is not False
                or not any(x in cand.get("announcement_title_unverified","") for x in ("复牌","恢复交易","恢复上市"))):
                raise ValueError("unsafe original resumption title selection")
            index_candidates[key]=cand
    text_by_key={}
    for doc in text_report["sources"]:
        key=(doc.get("issuer"),str(doc.get("announcement_id")))
        if key in text_by_key:raise ValueError("duplicate original text record")
        if doc.get("historical_PIT_verified") is not False:
            raise ValueError("PDF text promoted to PIT")
        text_by_key[key]=doc
    stored={};records=[];all_bytes=0;candidate_count=0
    for receipt_row in receipt["sources"]:
        key=(receipt_row.get("issuer"),str(receipt_row.get("announcement_id")))
        index_row=index_candidates.get(key);halt=source_by_issuer.get(key[0]);doc=text_by_key.get(key)
        if index_row is None or halt is None or doc is None:
            raise ValueError("PDF receipt not linked to original prior halt / index / extracted text")
        url=receipt_row.get("url")
        if url!=index_row.get("official_pdf_url"):
            raise ValueError("source PDF differs from official candidate URL")
        observed=receipt_row.get("original_bytes_verified") is True
        item={"issuer":key[0],"announcement_id":key[1],
              "official_pdf_url":url,
              "title_unverified":index_row.get("announcement_title_unverified"),
              "source_halt_text_day":halt["source_halt_date"],
              "source_halt_original_sha256":halt["source_halt_original_sha256"],
              "original_pdf_retrieved":observed,
              "historical_first_publication_authenticated":False,
              "actual_resumption_authenticated":False,
              "complete_halt_interval_certified":False}
        if observed:
            digest=receipt_row.get("sha256")
            if not isinstance(digest,str) or not SHA.fullmatch(digest):
                raise ValueError("missing original digest")
            name=key[0].replace(".","_")+"_"+key[1]+".pdf"
            if receipt_row.get("original_file")!=name:
                raise ValueError("unsafe original receipt filename")
            raw=(root/name).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=digest or not raw.startswith(b"%PDF-"):
                raise ValueError("raw original receipt does not match PDF")
            stamp=datetime.fromisoformat(receipt_row["observed_at_utc"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("invalid actual retrieval time")
            if doc.get("original_sha256")!=digest:
                raise ValueError("independent extracted text SHA differs")
            all_bytes+=len(raw)
            destination=f"pdf/{key[0].replace('.','_')}/{key[1]}/{digest}.pdf"
            stored[destination]=raw
            explicit=[];dedup=set()
            for context in doc.get("date_contexts_research_only",[]):
                if context.get("effective_date_certified") is not False:
                    raise ValueError("text date falsely authenticated")
                day=context["date_text"]
                result=classify(context["source_text_context"],day,"halt")
                if (result["local_textual_direction_candidate"]=="RESUME_START"
                    and doc.get("issuer_code_in_text") is True
                    and day not in dedup):
                    dedup.add(day)
                    explicit.append({"pdf_date_phrase":day,
                        "date_clause_unverified":result["source_clause_excerpt"],
                        "original_sha256":digest,
                        "first_publication_authenticated":False,
                        "resumption_date_authenticated":False})
            candidate_count+=len(explicit)
            item.update({"pdf_sha256":digest,"archival_pdf_path":destination,
                "bytes":len(raw),
                "retrieved_at_utc":stamp.astimezone(timezone.utc).isoformat(),
                "issuer_code_in_pdf_text_observed":doc.get("issuer_code_in_text") is True,
                "resume_same_clause_text_candidates":explicit})
        else:
            item["source_missing_does_not_prove_no_resumption"]=True
        records.append(item)
    if (all_bytes>MAX_PDF_BYTES or
        len(stored)!=receipt.get("retrieved")
        or any(x.get("historical_PIT_verified") is not False for x in receipt["sources"])):
        raise ValueError("unsupported original source / actual retrieval")
    manifest={"phase":"P3_RESUME_SOURCE_SHA_APPEND_ONLY_RESEARCH",
       "run_id":run_id,"source_halt_issuers_attempted":index["attempted"],
       "source_halt_records":sources,
       "source_index_states":[{"issuer":x["issuer"],"status":x["status"],"matching_titles":x["candidate_count"]} for x in index["results"]],
       "downloaded_resume_original_count":len(stored),
       "explicit_original_resume_text_candidates":candidate_count,
       "resume_notice_source_receipts":records,
       "publisher_first_publication_authenticated":False,
       "official_resume_effective_dates_certified":0,
       "continuous_halt_resume_intervals_certified":0,
       "historical_PIT_verified":False,
       "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    return manifest,stored

def verify_persisted(root,run_id):
    if type(run_id)!=int or run_id<=0:raise ValueError("invalid research run")
    root=Path(root)
    manifest=json.loads((root/"resume_runs"/f"{run_id}.json").read_text())
    if (manifest.get("phase")!="P3_RESUME_SOURCE_SHA_APPEND_ONLY_RESEARCH"
        or manifest.get("run_id")!=run_id
        or manifest.get("historical_PIT_verified") is not False
        or manifest.get("publisher_first_publication_authenticated") is not False
        or manifest.get("official_resume_effective_dates_certified")!=0
        or manifest.get("continuous_halt_resume_intervals_certified")!=0
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("orders")!=[]):
        raise ValueError("persisted research manifest appears executable")
    confirmed=0;total=0
    for source in manifest["resume_notice_source_receipts"]:
        if source.get("original_pdf_retrieved") is not True:continue
        digest=source["pdf_sha256"]
        if not SHA.fullmatch(digest):
            raise ValueError("invalid persisted SHA")
        expected=f"pdf/{source['issuer'].replace('.','_')}/{source['announcement_id']}/{digest}.pdf"
        if source.get("archival_pdf_path")!=expected:
            raise ValueError("unsafe recorded file path")
        data=(root/expected).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest or len(data)!=source["bytes"]:
            raise ValueError("persisted original PDF SHA diverged")
        if source.get("actual_resumption_authenticated") is not False:
            raise ValueError("unsupported effective resumption certification")
        total+=len(data);confirmed+=1
    if confirmed!=manifest["downloaded_resume_original_count"] or total>MAX_PDF_BYTES:
        raise ValueError("incomplete bounded resumption research archive")
    return {"phase":"P3_RESUME_SOURCE_ARCHIVE_SHA_REPLAY",
        "run_id":run_id,"source_issuers":manifest["source_halt_issuers_attempted"],
        "official_originals_sha_verified":confirmed,
        "same_clause_resumption_text_candidates":manifest["explicit_original_resume_text_candidates"],
        "official_resume_effective_dates_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",required=True,choices=("archive","verify"))
    p.add_argument("--index")
    p.add_argument("--originals")
    p.add_argument("--text")
    p.add_argument("--run-id",required=True,type=int)
    p.add_argument("--root")
    p.add_argument("--repo")
    a=p.parse_args()
    if a.mode=="archive":
        manifest,files=prepare(json.loads(Path(a.index).read_text()),a.originals,
            json.loads(Path(a.text).read_text()),a.run_id)
        status=persist(manifest,files,a.repo,namespace="resume_runs")
        print(json.dumps({"phase":"P3_RESUME_SOURCE_PERSISTED",
            "run_id":a.run_id,"originals_archived":len(files),
            "original_resume_text_leads":manifest["explicit_original_resume_text_candidates"],
            "branch":status["branch"],"trade_gate":"BLOCKED"}))
    else:
        print(json.dumps(verify_persisted(a.root,a.run_id)))
if __name__=="__main__":main()
