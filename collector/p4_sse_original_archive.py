"""Capture bounded official SSE HTML snapshots, preserving bytes and checksums.

Snapshots are research evidence, not exchange-calendar or PIT certification.
"""
import argparse,hashlib,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from collector.p4_sse_holiday_crosscheck import OFFICIAL_SSE_NOTICES

def capture(out,fetch=None):
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    result=[]
    for year,url in sorted(OFFICIAL_SSE_NOTICES.items()):
        record={"year":year,"source_url":url,"captured_utc":datetime.now(timezone.utc).isoformat()}
        try:
            if fetch:
                raw,final,status=fetch(url)
            else:
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=12) as response:
                    raw,final,status=response.read(3_000_001),response.geturl(),response.status
            host=urllib.request.urlparse(final).hostname or ""
            if status!=200 or not raw or len(raw)>3_000_000:raise ValueError("invalid response")
            if host!="sse.com.cn" and not host.endswith(".sse.com.cn"):
                raise ValueError("untrusted final host")
            name=f"sse_{year}.html"
            (root/name).write_bytes(raw)
            record.update(status="CAPTURED_OFFICIAL_HOST_CONTENT_UNVERIFIED",filename=name,
                          sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),final_url=final)
        except (OSError,ValueError) as error:
            record.update(status="SOURCE_UNAVAILABLE",error_type=type(error).__name__)
        result.append(record)
    summary={"phase":"P4_SSE_ORIGINAL_BYTE_ARCHIVE","receipts":result,
             "captured_count":sum(x["status"]=="CAPTURED_OFFICIAL_HOST_CONTENT_UNVERIFIED" for x in result),
             "expected_count":len(result),"historical_exchange_calendar_authenticated":False,
             "trade_gate":"BLOCKED","orders":[]}
    (root/"manifest.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    return summary
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True)
    result=capture(p.parse_args().out)
    print(json.dumps({"captured":result["captured_count"],"expected":result["expected_count"]}))
if __name__=="__main__":main()
