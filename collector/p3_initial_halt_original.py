"""Capture confirmed initial halt notice independently of mismatched resumption PDFs."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
URL="https://static.cninfo.com.cn/finalpage/2026-11-12/1225667574.PDF"
TOKENS=("600185","2026-073","停牌","重大资产重组","2026年11月12日")
def verify(text):
    s=re.sub(r"\s+","",text).replace("－","-").replace("—","-")
    return all(t in s for t in TOKENS)
def run(leads,root):
    if leads["trade_gate"]!="BLOCKED" or leads["orders"]!=[] or leads["executable_candidates"]!=[] or leads["official_certified"]!=0 or leads["historical_PIT_verified"] is not False:raise ValueError("unsafe input")
    rows=[r for r in leads["records"] if r["issuer"]=="sh.600185"]
    if len(rows)!=1 or rows[0]["start"]!="2026-11-12":raise ValueError("wrong target")
    root.mkdir(parents=True,exist_ok=True);p=root/"sh.600185-initial-halt.pdf"
    result=dict(issuer="sh.600185",url=URL,halt_start="2026-11-12",official_original_verified=False,resumption_verified=False,full_interval_verified=False,first_publication_verified=False,official_certified=False)
    try:
        subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),URL],check=True)
        raw=p.read_bytes()
        if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
        text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
        if not verify(text):raise ValueError("identity mismatch")
        result.update(official_original_verified=True,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name)
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        p.unlink(missing_ok=True);result.update(failure=type(e).__name__,failure_detail=str(e)[:200])
    return dict(asof=leads["asof"],record=result,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("leads","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.leads.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_INITIAL_HALT_ORIGINAL:",json.dumps(r))
