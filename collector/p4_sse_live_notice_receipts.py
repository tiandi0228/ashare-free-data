"""Bounded live official notice receipts. Failed fetches cannot be called authenticated."""
import argparse,hashlib,json,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from collector.p4_sse_holiday_crosscheck import OFFICIAL_SSE_NOTICES

def capture(fetch=None):
    def download(url):
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; ResearchEvidence/1.0)"})
        with urllib.request.urlopen(req,timeout=12) as response:
            return response.read(3_000_001),response.geturl(),response.status
    fetch=fetch or download
    evidence=[]
    for year,url in sorted(OFFICIAL_SSE_NOTICES.items()):
        item={"year":year,"url":url,"retrieved_at_utc":datetime.now(timezone.utc).isoformat()}
        try:
            raw,final,status=fetch(url)
            if status!=200 or not raw or len(raw)>3_000_000:raise ValueError("invalid bounded response")
            if "sse.com.cn" not in urllib.request.urlparse(final).hostname.split(".")[-3:]:
                raise ValueError("unexpected response host")
            item.update(status="FETCHED_OFFICIAL_HOST_UNVERIFIED_CONTENT",
                        final_url=final,byte_count=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        except (OSError,ValueError,urllib.error.URLError) as exc:
            item.update(status="SOURCE_UNAVAILABLE",error_type=type(exc).__name__)
        evidence.append(item)
    return {"phase":"P4_SSE_LIVE_NOTICE_FETCH_RECEIPTS","receipts":evidence,
            "fetched_count":sum(x["status"]=="FETCHED_OFFICIAL_HOST_UNVERIFIED_CONTENT" for x in evidence),
            "expected_count":len(evidence),"notice_content_matches_curated_closures":False,
            "historical_exchange_calendar_authenticated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    r=capture();out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"fetched_count":r["fetched_count"],"expected_count":r["expected_count"],"trade_gate":r["trade_gate"]}))
if __name__=="__main__":main()
