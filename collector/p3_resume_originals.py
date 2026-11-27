"""Verify four new retrospective resume originals; no PIT or fill promotion."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from datetime import date,timedelta
from collector.p3_next_originals import safe,missing
SOURCES={
"sh.601326":("https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1103/2026110302025_c.pdf",("601326","2026-031","2026-027","2026年10月21日","2026年11月4日","公司股票复牌公告"),"2026-10-21","2026-11-04",20000000),
"sz.000831":("https://static.cninfo.com.cn/finalpage/2026-11-14/1225671894.PDF",("000831","2026-043","2026-038","2026年11月2日","2026年11月16日","公司股票复牌"),"2026-11-02","2026-11-16",5000000),
"sz.002129":("https://static.cninfo.com.cn/finalpage/2026-11-14/1225672061.PDF",("002129","2026-069","2026-065","2026年11月2日","2026年11月16日","公司股票复牌"),"2026-11-02","2026-11-16",5000000),
"sz.002872":("https://static.cninfo.com.cn/finalpage/2026-11-21/1225682610.PDF",("002872","2026-059","2026年11月23日","2026年11月24日","撤销其他风险警示","日涨跌幅限制仍为10%"),"2026-11-23","2026-11-24",5000000)}
def days(start,end):
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if not a<b:raise ValueError("invalid interval")
    return [str(a+timedelta(days=i)) for i in range((b-a).days) if (a+timedelta(days=i)).weekday()<5]
def verify(text,tokens):
    return missing(text.replace("％","%").replace("–","-"),tokens)
def run(queue,prior,root):
    safe(queue);safe(prior)
    if prior["total_original_issuers_verified"]!=9:raise ValueError("wrong baseline")
    by={r["issuer"]:r for r in queue["tasks"]}
    if len(by)!=19 or len(queue["tasks"])!=19:raise ValueError("wrong queue")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,(url,tokens,start,resume,cap) in SOURCES.items():
        t=by[code];expected=days(start,resume)
        if t["vendor_nontradable_days"]!=expected or t["missing_expected_sessions"]:raise ValueError("vendor interval mismatch")
        p=root/(code+".pdf");r=dict(issuer=code,url=url,notice_halt_start=start,notice_resume=resume,vendor_days=expected,extension_sha256=t["extension_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False)
        try:
            subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","35","--max-filesize",str(cap),"--output",str(p),url],check=True,capture_output=True)
            raw=p.read_bytes()
            if not raw.startswith(b"%PDF-") or len(raw)>cap:raise ValueError("invalid PDF")
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=30)
            if code=="sh.601326":
                # HKEX contains multiple notices: limit identity checks to 031 section.
                s=re.sub(r"\s+","",text).replace("－","-").replace("—","-")
                m=re.search(r"公告编号[：:]2026-031",s)
                if not m:raise ValueError("missing 031 section")
                tail=s[m.start():];next_m=re.search(r"公告编号[：:]2026-032",tail)
                if not next_m:raise ValueError("missing section boundary")
                text=tail[:next_m.start()]
            r["missing_tokens"]=verify(text,tokens)
            if r["missing_tokens"]:raise ValueError("identity mismatch")
            r.update(official_original_verified=True,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name)
            if code=="sz.002872":r.update(notice_st_removed_effective=resume,notice_limit_pct="10.00",security_daily_reference_price_verified=False)
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_detail=str(e)[:200])
        records.append(r)
    n=sum(r["official_original_verified"] for r in records)
    return dict(asof=queue["asof"],attempted=len(records),new_originals_verified=n,total_original_issuers_verified=9+n,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","prior","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),json.loads(a.prior.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_RESUME_ORIGINALS:",json.dumps(r))
