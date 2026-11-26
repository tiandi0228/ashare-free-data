"""Scoped 002931 original notice retrieval and retrospective interval matching."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen

ISSUER="sz.002931"
PAIRS=(
 ("2026-01-14","2026-01-19","https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-01-14/5e4f661d-cdd6-4cf8-bbd3-b560a7754185.PDF","https://static.cninfo.com.cn/finalpage/2026-01-19/1224938833.PDF"),
 ("2026-01-26","2026-02-02","https://static.cninfo.com.cn/finalpage/2026-01-26/1224949020.PDF","https://static.cninfo.com.cn/finalpage/2026-02-02/1224960621.PDF"),
 ("2026-04-21","2026-04-27","https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-21/73612b06-0da2-471d-95a1-de4321ae6b9b.PDF","https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-04-25/965319f2-f975-4ee0-8ffd-88d8ac353983.PDF"),
)

def match(text,day,kind):
    compact=re.sub(r"\s+","",text)
    y,m,d=map(int,day.split("-"))
    token=f"{y}年{m}月{d}日"
    # Require the effective day and direction in the same short phrase.
    return "002931" in compact and bool(re.search(re.escape(token)+r".{0,35}?(?:开市起|开市时)"+kind,compact))

def run(queue, out):
    if queue["trade_gate"]!="BLOCKED" or queue["orders"]!=[] or queue["executable_candidates"]!=[]:
        raise ValueError("unsafe queue")
    task=next(t for t in queue["tasks"] if t["code"]==ISSUER)
    out.mkdir(parents=True,exist_ok=False)
    intervals=[]
    for start,end,halt,resume in PAIRS:
        notices=[]
        for day,url,kind in ((start,halt,"停牌"),(end,resume,"复牌")):
            with urlopen(url,timeout=35) as response:
                if response.geturl()!=url: raise ValueError("unexpected redirect")
                raw=response.read(8*1024*1024+1)
            if not raw.startswith(b"%PDF-") or len(raw)>8*1024*1024:
                raise ValueError("invalid PDF")
            name=day+("-halt.pdf" if kind=="停牌" else "-resume.pdf")
            p=out/name
            p.write_bytes(raw)
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True)
            if not match(text,day,kind):
                raise ValueError("notice does not support expected effective date "+day)
            notices.append(dict(url=url,sha256=hashlib.sha256(raw).hexdigest(),filename=name,
                                retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                                first_publication_authenticated=False))
        intervals.append(dict(start=start,resume=end,notices=notices))
    matches=[]
    for t in task["targets"]:
        hits=[i for i in intervals if i["start"]<=t["target_date"]<i["resume"]]
        if len(hits)!=1: raise ValueError("unmatched or ambiguous target")
        matches.append(dict(**t,halt_start=hits[0]["start"],resume_day=hits[0]["resume"],
                            historical_PIT_verified=False))
    return dict(issuer=ISSUER,intervals=intervals,matched_targets=matches,
                matched_target_days=len(matches),official_first_release_verified=False,
                officially_certified_halt_dates=0,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("queue",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=run(json.loads(a.queue.read_bytes()),a.out)
    (a.out/"report.json").write_text(json.dumps(r,indent=2)+"\n")
    print("002931_NOTICE_REPLAY:",json.dumps({k:v for k,v in r.items() if k not in ("intervals","matched_targets")}))
