"""P3 second-read PDF text anchors bound to first-read PDF SHA256.

This establishes repeatable *document text observation*, not issuance
authenticity, official market calendars, PIT timestamps, or trading permission.
Each PDF is downloaded again read-only, bounded and with redirects denied;
the second SHA256 must match the previously observed first-read digest.
A mismatch or missing pdftotext is UNKNOWN rather than source certification.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from collector.p3_curated_pdf_byte_probe import (
    EPOCH, MAX_BYTES, NeverRedirect, PER_DOC_TIMEOUT, safe_pdf_url
)

PHASE="P3_SECOND_READ_PDF_SHA256_AND_TEXT_ANCHOR_RESEARCH"
PRIORITY={
    "sh.601238": ("2026-049", "广汽集团", "停牌"),
    "sh.603517": ("2026-080", "绝味食品", "风险警示"),
    "sh.603838": ("2026-040", "四通股份", "风险警示"),
}
CORROBORATION_ONLY = frozenset(("证券代码","股票代码","公告编号"))
def normalized(text):
    text=unicodedata.normalize("NFKC",text)
    return "".join(text.split()).replace("—","-").replace("－","-").replace("–","-")

def download_same_pdf(url, expected_sha, opener, pdf_to_text):
    safe_pdf_url(url)
    if not isinstance(expected_sha,str) or not re.fullmatch(r"[0-9a-f]{64}",expected_sha):
        raise ValueError("invalid first-read SHA256")
    out={"url":url,"second_read_sha256":None,"same_bytes_as_first_read":False,
        "text_extracted":False,"normalized_text":None,
        "status":"UNAVAILABLE_OR_UNAUTHENTICATED"}
    try:
        req=urllib.request.Request(url,headers={"Accept":"application/pdf",
             "User-Agent":"StockMateResearchReadonlyPDFSHA/1.0"},method="GET")
        with opener.open(req,timeout=PER_DOC_TIMEOUT) as stream:
            if stream.status!=200:return out
            length=stream.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or int(length)>MAX_BYTES):
                return out
            # Bounded in memory. No PDF binary persisted to Git or artifacts.
            raw=stream.read(MAX_BYTES+1)
            if not 32<=len(raw)<=MAX_BYTES or not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
                return out
        h=hashlib.sha256(raw).hexdigest()
        out["second_read_sha256"]=h
        out["same_bytes_as_first_read"]=h==expected_sha
        if h!=expected_sha:
            out["status"]="SOURCE_PDF_BYTES_CHANGED_BETWEEN_READS"
            return out
        if pdf_to_text is None:
            out["status"]="NO_PDF_TEXT_EXTRACTOR"
            return out
        txt=pdf_to_text(raw)
        if not isinstance(txt,str) or not txt.strip():
            out["status"]="PDF_TEXT_EXTRACTION_EMPTY"
            return out
        out["text_extracted"]=True
        out["normalized_text"]=normalized(txt)
        out["status"]="MATCHING_SHA_PDF_TEXT_EXTRACTED_NOT_PIT_CERTIFIED"
        return out
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError,
            ValueError,subprocess.TimeoutExpired,subprocess.SubprocessError):
        return out

def extractor(raw):
    if not shutil.which("pdftotext"):
        return ""
    done=subprocess.run(
        ["pdftotext","-layout","-enc","UTF-8","-","-"],
        input=raw,capture_output=True,timeout=10,check=False)
    if done.returncode!=0:return ""
    return done.stdout.decode("utf-8","replace")

def evaluate(manifest,first,opener,download=download_same_pdf,pdf_to_text=extractor):
    if (manifest.get("phase")!="P3_EIGHT_PREVIOUSLY_UNLINKED_ISSUER_DATED_DISCLOSURE_RESEARCH_V1"
        or manifest.get("source_epoch_sha256")!=EPOCH
        or manifest.get("historical_PIT_verified") is not False
        or manifest.get("trade_gate")!="BLOCKED"
        or first.get("phase")!="P3_CURATED_ISSUER_PDF_BYTE_SHA256_READ_ONLY_PROBE"
        or first.get("source_epoch_sha256")!=EPOCH
        or first.get("trade_gate")!="BLOCKED"
        or first.get("source_pdf_original_bytes_authenticity_certified") is not False
        or first.get("full_historical_exchange_PIT_certified") is not False):
        raise ValueError("research input falsely claims source certification")
    receipts=first.get("pdf_byte_hash_receipts")
    if not isinstance(receipts,list) or len(receipts)!=9:
        raise ValueError("expected nine first-read URL receipts")
    indexed={}
    for r in receipts:
        if not isinstance(r,dict) or r.get("url") in indexed:
            raise ValueError("duplicate or malformed first read")
        indexed[r.get("url")]=r
    cases={c["issuer"]:c for c in manifest.get("cases",[])}
    if not set(PRIORITY).issubset(cases):
        raise ValueError("missing priority issuer")
    rows=[]
    for issuer,(number,company,term) in PRIORITY.items():
        case=cases[issuer]
        pdfs=[d for d in case["documents"] if d.get("reference_class")=="issuer_pdf_indexed"
              and d.get("announcement")==number]
        if len(pdfs)!=1:
            raise ValueError("priority notice not uniquely identified")
        doc=pdfs[0]
        url=safe_pdf_url(doc["url"])
        old=indexed.get(url)
        if not old:
            raise ValueError("missing bound PDF byte receipt")
        result={"issuer":issuer,"claimed_announcement":number,
            "notice_url":url,"source_original_csv_sha256":case["original_csv_sha256"],
            "first_read_sha256":old.get("sha256"),
            "first_read_outcome":old.get("fetch_outcome"),
            "document_code_anchor":False,"announcement_number_anchor":False,
            "company_anchor":False,"critical_term_anchor":False,
            "issuer_and_notice_text_observed":False,
            "historical_trading_day_authorized":False,
            "historical_ST_period_certified":False,
            "original_pdf_content_independently_authenticated":False,
            "official_PIT_session_authenticated":False}
        if (old.get("fetch_outcome")=="PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED"
            and isinstance(old.get("sha256"),str)):
            evidence=download(url,old["sha256"],opener,pdf_to_text)
            raw=evidence.pop("normalized_text",None)
            result.update(evidence)
            if evidence["same_bytes_as_first_read"] and evidence["text_extracted"] and raw:
                code=issuer.split(".")[1]
                result["document_code_anchor"]=code in raw
                result["announcement_number_anchor"]=normalized(number) in raw
                result["company_anchor"]=normalized(company) in raw
                result["critical_term_anchor"]=normalized(term) in raw
                result["issuer_and_notice_text_observed"]=all(
                    result[k] for k in ("document_code_anchor","announcement_number_anchor",
                                        "company_anchor","critical_term_anchor"))
                if issuer=="sh.601238":
                    result["has_2026_september_14_claim"]="2026年9月14日" in raw
                    result["has_2026_september_15_claim"]="2026年9月15日" in raw
                    result["halt_effective_day_status"]="UNRESOLVED_CONFLICT_REQUIRES_EXCHANGE_DAY_PROOF"
                else:
                    result["has_2026_october_20_claim"]="2026年10月20日" in raw
                    result["st_lookback_status"]="REJECT_PRE_REMOVAL_AS_ELIGIBLE"
            else:
                result["halt_effective_day_status"]="UNAUTHENTICATED"
        else:
            result["status"]="FIRST_READ_PDF_UNAVAILABLE"
        rows.append(result)
    return {
        "phase":PHASE,"source_epoch_sha256":EPOCH,
        "priority_issuer_count":3,
        "same_bytes_twice_count":sum(bool(x.get("same_bytes_as_first_read")) for x in rows),
        "issuer_notice_and_term_text_observed_count":sum(
            x["issuer_and_notice_text_observed"] for x in rows),
        "content_sha256_is_NOT_issuer_authenticity":True,
        "guangqi_conflicting_halt_date_unresolved":True,
        "pre_st_removal_dates_conservatively_excluded":True,
        "full_issuer_halt_calendar_certified":False,
        "historical_PIT_verified":False,
        "feature_shards_promoted":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "rows":rows,
    }

def main():
    p=argparse.ArgumentParser()
    for key in ("manifest","first-probe","out"):
        p.add_argument("--"+key,type=Path,required=True)
    args=p.parse_args()
    opener=urllib.request.build_opener(
        urllib.request.ProxyHandler({}),NeverRedirect())
    result=evaluate(json.loads(args.manifest.read_text()),
        json.loads(args.first_probe.read_text()),opener)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("P3_PDF_ANCHOR_SECOND_READ",json.dumps({
        "double_sha_matched":result["same_bytes_twice_count"],
        "priority_issuer_text_anchors":result["issuer_notice_and_term_text_observed_count"],
        "PIT_certified":False,"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
