"""Capture alternative free official SSE PDF originals after primary IPO HTML returns 403.

A PDF that was published after IPO may corroborate an IPO date retrospectively,
but must never be used as evidence of historical point-in-time knowledge.
"""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

SOURCES=[
 {"id":"cninfo_2025_ipo_original","url":"https://static.cninfo.com.cn/finalpage/2025-05-16/1223557376.PDF","published_day":"2025-05-16"},
 {"id":"sse_2025_official_report","url":"https://big5.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-11-01/603014_20251101_6P01.pdf","published_day":"2025-11-01"},
 {"id":"sse_2026_official_report","url":"https://static.sse.com.cn/stock/disclosure/announcement/c/202603/603014_20260311_U7PK.pdf","published_day":"2026-03-11"}
]
def capture_one(source,out):
    result={"source_id":source["id"],"url":source["url"],"published_day":source["published_day"],
            "source_status":"UNVERIFIED","original_bytes_verified":False,
            "listing_day_text_verified":False,"historic_PIT_publication_verified":False,
            "historical_ipo_notice_verified":False}
    try:
        req=Request(source["url"],headers={"User-Agent":"Mozilla/5.0","Accept":"application/pdf"})
        with urlopen(req,timeout=25) as response:
            raw=response.read(15000001)
        if not raw.startswith(b"%PDF-") or len(raw)>15000000 or len(raw)<3000:
            raise ValueError("not a bounded PDF original")
        dest=Path(out)/(source["id"]+".pdf")
        dest.write_bytes(raw)
        result.update(source_status="PDF_BYTES_OBSERVED",original_bytes_verified=True,
                      sha256=hashlib.sha256(raw).hexdigest(),original_bytes=len(raw),
                      acquired_at_utc=datetime.now(timezone.utc).isoformat())
        try:
            from pypdf import PdfReader
            reader=PdfReader(str(dest))
            page_text="".join(page.extract_text() or "" for page in reader.pages[:100])
            compact="".join(page_text.split())
            has_code="603014" in compact
            has_date=any(s in compact for s in ("2025年5月19日","2025-05-19","2025/5/19","2025.5.19"))
            result["extracted_page_count"]=min(len(reader.pages),100)
            result["code_text_observed"]=has_code
            result["date_text_observed"]=has_date
            if has_code and has_date:
                result.update(listing_day_text_verified=True,source_status="RETROSPECTIVE_PDF_LISTING_DAY_TEXT_OBSERVED")
            else:
                result["parse_diagnostic"]="extracted text does not establish both issuer and listing date"
        except Exception as exc:
            result["parse_diagnostic"]=type(exc).__name__
    except (HTTPError,URLError,ValueError,TimeoutError) as exc:
        result.update(source_status="SOURCE_ACCESS_FAILED",
                      failure_type=type(exc).__name__,
                      http_status=exc.code if isinstance(exc,HTTPError) else None)
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    a=p.parse_args()
    d=Path(a.out);d.mkdir(parents=True,exist_ok=True)
    results=[capture_one(source,d) for source in SOURCES]
    summary={"phase":"P1_603014_OFFICIAL_FREE_SOURCE_FALLBACK",
             "sources":results,"official_PIT_universe_verified":False,
             "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    (d/"fallback_quality.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+chr(10))
    print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
