"""Capture and independently substantiate 603014 SSE listing notice as observed source."""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from collector.p1_603014_official_ipo_gap_reconcile import OFFICIAL

def capture(raw):
    text=raw.decode("utf-8")
    if len(raw)<1000 or len(raw)>400000:
        raise ValueError("implausible official HTML length")
    plain=re.sub(r"<[^>]*>"," ",text)
    plain=re.sub(r"\\s+","",plain)
    conditions=("山东威高血液净化制品股份有限公司","上证公告（股票）[2025]15号",
                "2025年5月19日","603014","上海证券交易所")
    if not all(c in plain for c in conditions):
        raise ValueError("official issuer, listing date or announcement identity absent")
    # Extract as separately observed evidence; never backdate receipt to 2025.
    return {"phase":"P1_603014_SSE_ORIGINAL_HTML_RECEIPT",
            "url":OFFICIAL["url"],"source_host":"www.sse.com.cn",
            "sha256":hashlib.sha256(raw).hexdigest(),"original_bytes":len(raw),
            "issuer":OFFICIAL["issuer"],"notice_day":"2025-05-16",
            "first_trading_day":"2025-05-19",
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "original_html_observed":True,
            "historical_publication_instant_verified":False,
            "historical_PIT_membership_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--raw",required=True)
    a=p.parse_args()
    req=Request(OFFICIAL["url"],headers={"User-Agent":"Mozilla/5.0 research provenance verifier"})
    try:
        with urlopen(req,timeout=25) as response:
            raw=response.read(400001)
        r=capture(raw)
        path=Path(a.raw);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    except (HTTPError,URLError,TimeoutError,ValueError,UnicodeError) as exc:
        r={"phase":"P1_603014_SSE_ORIGINAL_HTML_RECEIPT","url":OFFICIAL["url"],
           "source_status":"UNAVAILABLE_OR_CONTENT_UNVERIFIED",
           "failure_type":type(exc).__name__,
           "http_status":exc.code if isinstance(exc,HTTPError) else None,
           "original_html_observed":False,
           "historical_publication_instant_verified":False,
           "historical_PIT_membership_verified":False,
           "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    Path(a.out).write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(r,ensure_ascii=False))
if __name__=="__main__":main()
