"""Retrospective issuer-disclosure corroboration, not first-publication proof."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from urllib.request import urlopen
from datetime import datetime,timezone

SOURCES=(
("2026-01-07","https://disc.static.szse.cn/disc/disk03/finalpage/2026-01-07/a253690c-40cf-48ab-8fa2-fff95d136a23.PDF",r"2026年1月7日.{0,25}开市起停牌"),
("2026-02-11","https://static.cninfo.com.cn/finalpage/2026-02-11/1224975451.PDF",r"2026年1月7日.{0,15}1月26日.{0,15}停牌核查.{0,30}1月12日.{0,15}2月2日.{0,20}复牌"),
("2026-06-05","https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-06-05/d46e2254-f514-4b6a-8a11-2cb19fd283d8.PDF",r"2026年6月5日.{0,25}开市起复牌"),
)

def run(queue,out):
    assert queue["trade_gate"]=="BLOCKED" and queue["orders"]==queue["executable_candidates"]==[]
    task=next(t for t in queue["tasks"] if t["code"]=="sz.002969")
    assert {t["target_date"] for t in task["targets"]}=={"2026-01-08","2026-01-09","2026-01-28","2026-06-03"}
    out.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for day,url,pattern in SOURCES:
        r=dict(day=day,url=url,verified=False,first_publication_authenticated=False)
        try:
            with urlopen(url,timeout=35) as response:
                if response.geturl()!=url:raise ValueError("redirect")
                raw=response.read(8388609)
            if not raw.startswith(b"%PDF-") or len(raw)>8388608:raise ValueError("invalid PDF")
            p=out/(day+".pdf")
            p.write_bytes(raw)
            text=re.sub(r"\s+","",subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=20))
            if "002969" not in text or not re.search(pattern,text):raise ValueError("issuer or date phrase mismatch")
            r.update(verified=True,sha256=hashlib.sha256(raw).hexdigest(),filename=p.name,retrieved_at_utc=datetime.now(timezone.utc).isoformat())
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            r.update(error=type(e).__name__,detail=str(e)[:200])
        receipts.append(r)
    # Later issuer notice corroborates both January intervals; it cannot prove
    # their first publication or replace independent halt/resume original pairs.
    confirmed=receipts[1]["verified"]
    matches=[t for t in task["targets"] if confirmed and t["target_date"] in ("2026-01-08","2026-01-09","2026-01-28")]
    return dict(issuer="sz.002969",receipts=receipts,retrospective_matches=matches,
                retrospective_target_days=len(matches),originals_verified=sum(r["verified"] for r in receipts),
                complete_original_pairs=0,officially_certified_halt_dates=0,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("queue",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),a.out)
    (a.out/"report.json").write_text(json.dumps(r,indent=2)+"\n")
    print("002969_RETROSPECTIVE_REPLAY:",json.dumps({k:v for k,v in r.items() if k not in ("receipts","retrospective_matches")}))
