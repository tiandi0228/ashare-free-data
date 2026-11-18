"""Read-only bounded SHA256 probing of curated issuer PDF URLs (NOT PIT certification).

Exactly the nine cninfo PDF references in the reviewed P3 research fixture.
No redirects, credentials, raw PDF persistence, publisher reprint downloads,
external command execution, or remote state mutation. Download outcomes are
diagnostics; failed/blocked PDFs never become valid source evidence.
"""
import argparse
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
PHASE="P3_CURATED_ISSUER_PDF_BYTE_SHA256_READ_ONLY_PROBE"
PDF_PATH=re.compile(r"/finalpage/2026-(?:09|10)-[0-3][0-9]/[0-9]+\.PDF\Z")
MAX_BYTES=12*1024*1024
PER_DOC_TIMEOUT=12

class NeverRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def safe_pdf_url(url):
    if not isinstance(url,str):
        raise ValueError("invalid PDF URL")
    p=urllib.parse.urlsplit(url)
    if (p.scheme!="https" or p.netloc!="static.cninfo.com.cn"
        or p.username or p.password or p.query or p.fragment
        or not PDF_PATH.fullmatch(p.path)):
        raise ValueError("PDF source is not on exact approved CNINFO path")
    return url

def probe_one(url,opener):
    safe_pdf_url(url)
    result={
        "url":url,"network_attempted":True,"http_status":None,
        "fetch_outcome":"UNAVAILABLE","byte_count":None,
        "observed_pdf_magic":False,"sha256":None,
        "document_semantics_authenticated":False,
        "first_publication_instant_authenticated":False,
        "official_exchange_pit_certified":False
    }
    try:
        req=urllib.request.Request(url,headers={
            "User-Agent":"StockMateResearchReadonlyPDFSHA/1.0",
            "Accept":"application/pdf",
        },method="GET")
        with opener.open(req,timeout=PER_DOC_TIMEOUT) as f:
            status=f.status
            result["http_status"]=status
            if status!=200:
                result["fetch_outcome"]="NON_200_HTTP"
                return result
            length=f.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length)>MAX_BYTES):
                result["fetch_outcome"]="OVER_SIZE_OR_INVALID_LENGTH"
                return result
            digest=hashlib.sha256()
            total=0
            first=b""
            tail=b""
            while True:
                chunk=f.read(65536)
                if not chunk:break
                total+=len(chunk)
                if total>MAX_BYTES:
                    result["fetch_outcome"]="OVER_SIZE_OR_INVALID_LENGTH"
                    return result
                if len(first)<8:
                    first=(first+chunk)[:8]
                tail=(tail+chunk)[-2048:]
                digest.update(chunk)
            if total<32 or not first.startswith(b"%PDF-") or b"%%EOF" not in tail:
                result["fetch_outcome"]="NOT_VALID_PDF_ENVELOPE"
                return result
            result.update({
                "byte_count":total,"observed_pdf_magic":True,
                "sha256":digest.hexdigest(),
                "fetch_outcome":"PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED",
            })
            return result
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,
            OSError,ssl.SSLError,ValueError) as exc:
        result["fetch_outcome"]="FETCH_FAILED_"+type(exc).__name__
        return result

def run(manifest,opener,probe=probe_one):
    if (not isinstance(manifest,dict)
        or manifest.get("source_epoch_sha256")!=EPOCH
        or manifest.get("phase")!="P3_EIGHT_PREVIOUSLY_UNLINKED_ISSUER_DATED_DISCLOSURE_RESEARCH_V1"
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("source_pdf_bytes_sha_verified") is not False
        or manifest.get("historical_PIT_verified") is not False
        or manifest.get("orders")!=[] or manifest.get("executable_candidates")!=[]):
        raise ValueError("untrusted P3 research manifest")
    cases=manifest.get("cases")
    if not isinstance(cases,list) or len(cases)!=8:
        raise ValueError("expected eight source issuer records")
    rows=[];urls=set();seen=set()
    for case in cases:
        issuer=case.get("issuer")
        if issuer in seen or not re.fullmatch(r"(?:sh|sz)\.\d{6}",issuer or ""):
            raise ValueError("duplicate or invalid issuer")
        seen.add(issuer)
        for doc in case.get("documents",[]):
            if doc.get("reference_class")!="issuer_pdf_indexed":
                continue
            url=safe_pdf_url(doc.get("url"))
            if url in urls:
                raise ValueError("duplicate PDF URL across issuer records")
            urls.add(url)
            if len(urls)>12:raise ValueError("unexpected additional PDF references")
            if doc.get("content_sha256") is not None:
                raise ValueError("input falsely asserts verified bytes")
            info=probe(url,opener)
            if info.get("url")!=url or info.get("official_exchange_pit_certified") is not False:
                raise ValueError("invalid downloader result")
            rows.append({"issuer":issuer,"announcement":doc["announcement"],
                         "announcement_day_claim":doc["date"],**info})
    if len(rows)!=9:
        raise ValueError("unexpected source PDF count")
    return {
        "phase":PHASE,
        "source_epoch_sha256":EPOCH,
        "approved_issuer_count":8,"approved_pdf_url_count":len(rows),
        "downloaded_pdf_with_sha_count":sum(
            x["fetch_outcome"]=="PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED" for x in rows),
        "failed_or_unavailable_pdf_count":sum(
            x["fetch_outcome"]!="PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED" for x in rows),
        "pdf_byte_hash_receipts":rows,
        "source_pdf_original_bytes_authenticity_certified":False,
        "pdf_contents_issuer_code_announcement_matching_certified":False,
        "full_historical_exchange_PIT_certified":False,
        "research_links_issuer_count":15,
        "original_p2_gap_issuers_remaining":16,
        "source_feature_shards_promoted":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "original_csv_archive_modified":False,
        "publisher_reprint_approvals":0,
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    opener=urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NeverRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    result=run(json.loads(args.manifest.read_text()),opener)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("P3_PDF_BYTES_READ_ONLY_PROBE",json.dumps({
        "attempted":result["approved_pdf_url_count"],
        "pdf_bytes_hashed":result["downloaded_pdf_with_sha_count"],
        "unavailable":result["failed_or_unavailable_pdf_count"],
        "full_PIT_certified":False,"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
