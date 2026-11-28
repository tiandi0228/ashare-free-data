"""Reconcile three newly located CNINFO originals with frozen vendor halt dates."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
SOURCES={
"sh.603580":("https://static.cninfo.com.cn/finalpage/2026-11-21/1225681895.PDF",("603580","2026-080","要约收购","2026/11/23","2026/11/24","停牌一个交易日"),["2026-11-23"],"HALT_AND_PLANNED_RESUME"),
"sh.605255":("https://static.cninfo.com.cn/finalpage/2026-11-19/1225678240.PDF",("605255","2026-062","停牌核查结果","2026/11/18","2026/11/19","2026年11月16日"),["2026-11-16","2026-11-17","2026-11-18"],"RETROSPECTIVE_HALT_RESUME"),
"sh.605258":("https://static.cninfo.com.cn/finalpage/2026-10-24/1225620941.PDF",("605258","2026-021","控制权变更","2026年10月26日","不超过2个交易日"),["2026-10-26","2026-10-27","2026-10-28","2026-10-29","2026-10-30"],"INITIAL_HALT_ONLY"),
}
def missing(text,tokens):
    s=re.sub(r"\s+","",text).replace("－","-").replace("—","-")
    return [t for t in tokens if t not in s]
def safe(r):
    if r["asof"]!="2026-11-25" or r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["official_certified"]!=0 or r["historical_PIT_verified"] is not False:raise ValueError("unsafe source")
def run(queue,prior,root):
    safe(queue);safe(prior)
    if prior["total_original_issuers_verified"]!=6:raise ValueError("wrong prior scope")
    by={r["issuer"]:r for r in queue["tasks"]}
    if len(by)!=19 or len(queue["tasks"])!=19:raise ValueError("wrong queue")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,(url,tokens,days,kind) in SOURCES.items():
        t=by[code]
        if t["vendor_nontradable_days"]!=days or t["missing_expected_sessions"]:raise ValueError("vendor interval mismatch")
        p=root/(code+".pdf")
        r=dict(issuer=code,url=url,kind=kind,vendor_days=days,extension_sha256=t["extension_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False)
        try:
            subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),url],check=True,capture_output=True)
            raw=p.read_bytes()
            if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
            r["missing_tokens"]=missing(text,tokens)
            if r["missing_tokens"]:raise ValueError("identity mismatch")
            r.update(official_original_verified=True,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name)
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_detail=str(e)[:200])
        records.append(r)
    n=sum(r["official_original_verified"] for r in records)
    return dict(asof=queue["asof"],attempted=len(records),new_originals_verified=n,total_original_issuers_verified=6+n,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","prior","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),json.loads(a.prior.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_NEXT_ORIGINALS:",json.dumps(r))
