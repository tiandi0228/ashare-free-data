"""Retrospective notice leads only; source bytes captured on explicit PR CI, not PIT."""
import argparse,hashlib,json,subprocess,re
from pathlib import Path
LEADS=(
 ("sh.603030","2026-11-18","2026-11-20","2026-046","https://big5.sse.com.cn/site/cht/www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-11-20/603030_20261120_5NAS.pdf","2026年11月18日"),
 ("sh.603396","2026-11-11","2026-11-16","2026-069","https://static.cninfo.com.cn/finalpage/2026-11-16/1225672373.PDF","2026年11月11日"),
)
def assess(queue,root):
    if queue["trade_gate"]!="BLOCKED" or queue["orders"]!=[] or queue["executable_candidates"]!=[] or queue["official_limit_certified"]!=0 or queue["historical_PIT_verified"] is not False:raise ValueError("unsafe source")
    keys={(r["code"],r["day"]) for r in queue["tasks"] if r["priority"]=="P1_DIRECTIONAL"}
    if len(keys)!=23:raise ValueError("unexpected queue")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,day,pub,number,url,token in LEADS:
        if (code,day) not in keys or pub<=day:raise ValueError("wrong retrospective target")
        p=root/(code+"-"+day+".pdf")
        subprocess.run(["curl","--fail","--silent","--show-error","--location","--max-time","30","--max-filesize","5000000","--output",str(p),url],check=True)
        raw=p.read_bytes()
        if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("not PDF")
        s=subprocess.check_output(["pdftotext","-layout",str(p),"-"],timeout=30).decode("utf-8")
        s=re.sub(r"\s+","",s).replace("－","-").replace("–","-")
        if not all(t in s for t in (code.split(".")[1],number,token,"股票交易风险提示公告","涨幅偏离值")):raise ValueError("document identity mismatch")
        records.append(dict(code=code,day=day,notice_date=pub,notice_number=number,url=url,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name,evidence_type="RETROSPECTIVE_MULTI_DAY_ABNORMAL_MOVE_NOTICE",official_limit_verified=False,first_publication_verified=False,fill_verified=False))
    return dict(asof=queue["asof"],priority_targets=len(keys),original_notice_leads=len(records),official_limit_certified=0,historical_PIT_verified=False,execution_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=assess(json.loads(a.queue.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_NOTICE_LEADS:",json.dumps(r))
