"""One fixed official disclosure-platform 2026-05-23 issuer restart PDF.

Source may discuss an intended June 1 resume / delisting arrangement,
but no proof of issuer tradability or original as-of publication timestamp.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request,urlopen

from collector.cninfo_issuer_pdf_probe import extract_pdf_text

URL="https://static.cninfo.com.cn/finalpage/2026-05-23/1225327963.PDF"
MAX_BYTES=3_000_000
MAX_PAGES=12

def get(url):
    req=Request(url,headers={
        "User-Agent":"ashare-free-data-research-provenance/1.0",
        "Accept-Encoding":"identity",
    })
    with urlopen(req,timeout=16) as response:
        if response.geturl()!=URL:
            raise ValueError("Unexpected original PDF redirect")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("Original PDF exceeds budget")
    return raw, URL

def verify(raw,url,text,pages):
    if url!=URL:
        raise ValueError("Unexpected source URL")
    if not raw.startswith(b"%PDF-") or len(raw)>MAX_BYTES or not 1<=pages<=MAX_PAGES:
        raise ValueError("PDF header, page count or size invalid")
    normalized=re.sub(r"\s+","",text)
    anchors=(
        "湖北华嵘控股股份有限公司",
        "600421",
        "退市整理期",
        "2026年6月1日",
    )
    if not all(x in normalized for x in anchors):
        raise ValueError("Missing anchored issuer restart/delisting text")
    return {
        "source_url":url,
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "original_pdf_bytes":len(raw),
        "original_pdf_pages":pages,
        "url_date":"2026-05-23",
        "source_issuer":"sh.600421",
        "event_type":"ISSUER_DELISTING_CONSOLIDATION_NOTICE",
        "issuer_stated_resumption_date":"2026-06-01",
        "tradability_on_resumption_date_exchange_verified":False,
        "official_st_status_history_covered":False,
        "original_issuer_publication_instant_verified":False,
        "source_pdf_cryptographic_publisher_signature_verified":False,
        "original_pdf_redistributed":False,
    }

def run(out,fetch=get,extract=extract_pdf_text):
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    q={
        "phase":"P3_CNINFO_600421_EARLY_DELIST_RISK_PDF",
        "status":"BLOCKED_NO_SOURCE",
        "attempted_https_gets":1,
        "first_party_exchange_signed_state":False,
        "all_market_ST_halt_delist_covered":False,
        "historical_asof_certified":False,
        "paid_api_calls":0,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
    }
    try:
        raw,url=fetch(URL)
        text,pages=extract(raw)
        q.update(verify(raw,url,text,pages))
        q["status"]="ISSUER_EARLY_NOTICE_OBSERVED_UNVERIFIED_PIT"
    except (ValueError,OSError,UnicodeError,TimeoutError,TypeError,KeyError) as exc:
        q["failure_type"]=type(exc).__name__
    q["observed_utc"]=datetime.now(timezone.utc).isoformat()
    (dest/"quality.json").write_text(json.dumps(q,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(q,ensure_ascii=False))
    return 0 if q["status"]=="ISSUER_EARLY_NOTICE_OBSERVED_UNVERIFIED_PIT" else 2

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    a=p.parse_args()
    raise SystemExit(run(a.out))
