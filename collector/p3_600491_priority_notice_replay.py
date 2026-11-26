"""600491 original disclosure leads: partial evidence, never PIT certification."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.request import urlopen
from datetime import datetime, timezone

ISSUER="sh.600491"
# Each source is checked for the issuer and an exact effective-date phrase.
SOURCES=(
 ("2026-04-30","halt","https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/600491_20260430_AQNG.pdf",r"2026年4月30日停牌"),
 ("2026-07-03","halt","https://static.cninfo.com.cn/finalpage/2026-07-03/1225407586.PDF",r"2026年7月3日.{0,15}开市起停牌"),
 ("2026-08-28","resume","https://static.cninfo.com.cn/finalpage/2026-08-28/1225518255.PDF",r"2026年8月28日.{0,15}开市起复牌"),
)

def run(queue,out):
    if queue["trade_gate"]!="BLOCKED" or queue["orders"]!=[] or queue["executable_candidates"]!=[]:
        raise ValueError("unsafe queue")
    task=next(t for t in queue["tasks"] if t["code"]==ISSUER)
    if {t["target_date"] for t in task["targets"]}!={"2026-04-30","2026-07-03","2026-08-27"}:
        raise ValueError("unexpected priority targets")
    out.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for day,kind,url,pattern in SOURCES:
        result=dict(day=day,kind=kind,url=url,original_verified=False,first_publication_authenticated=False)
        try:
            with urlopen(url,timeout=35) as response:
                if response.geturl()!=url: raise ValueError("unexpected redirect")
                raw=response.read(8*1024*1024+1)
            if not raw.startswith(b"%PDF-") or len(raw)>8*1024*1024:
                raise ValueError("invalid PDF")
            p=out/(day+"-"+kind+".pdf")
            p.write_bytes(raw)
            text=re.sub(r"\s+","",subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=20))
            if "600491" not in text or not re.search(pattern,text): raise ValueError("effective date phrase not verified")
            result.update(original_verified=True,sha256=hashlib.sha256(raw).hexdigest(),filename=p.name,retrieved_at_utc=datetime.now(timezone.utc).isoformat())
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            result.update(error=type(e).__name__,detail=str(e)[:200])
        receipts.append(result)
    return dict(issuer=ISSUER,targets=task["targets"],receipts=receipts,
                originals_verified=sum(r["original_verified"] for r in receipts),
                matched_target_days=sum(r["original_verified"] and r["kind"]=="halt" for r in receipts),
                complete_intervals_verified=0,officially_certified_halt_dates=0,
                historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("queue",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=run(json.loads(a.queue.read_bytes()),a.out)
    (a.out/"report.json").write_text(json.dumps(r,indent=2)+"\n")
    print("600491_PARTIAL_NOTICE_REPLAY:",json.dumps({k:v for k,v in r.items() if k not in ("targets","receipts")}))
