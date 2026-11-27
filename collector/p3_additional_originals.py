"""Two scoped exchange originals; validate notice facts, not first publication or execution."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
SOURCES={
"sz.000820":("https://disc.static.szse.cn/disc/disk03/finalpage/2026-11-25/cbb1798d-9e48-4186-9358-84b0e420d8e5.PDF",("000820","2026-078","2026年11月25日","2026年11月26日","实施其他风险警示","ST节能","涨跌幅限制不变","10%"),"ST_CHANGE_NOTICE", "2026-11-25"),
"sh.600567":("https://big5.sse.com.cn/site/cht/www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-11-19/600567_20261119_GTM1.pdf",("600567","2026-075","筹划重大事项","停牌","2026年11月19日"),"INITIAL_HALT_NOTICE","2026-11-19"),
}
def verify(text,tokens):
    s=re.sub(r"\s+","",text).replace("－","-").replace("—","-").replace("％","%")
    return [t for t in tokens if t not in s]
def run(leads,pinned,root):
    for r in (leads,pinned):
        if r["asof"]!="2026-11-25" or r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["official_certified"]!=0 or r["historical_PIT_verified"] is not False:raise ValueError("unsafe source")
    if pinned["original_issuers_verified"]!=4:raise ValueError("wrong baseline")
    by={r["issuer"]:r for r in leads["records"]}
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,(url,tokens,kind,start) in SOURCES.items():
        t=by[code]
        if t["start"]!=start or t["vendor_days"][0]!=start:raise ValueError("wrong target")
        p=root/(code+".pdf")
        r=dict(issuer=code,url=url,kind=kind,extension_sha256=t["extension_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False,resume_vendor_observed=False)
        try:
            subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),url],check=True,capture_output=True)
            raw=p.read_bytes()
            if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
            r["missing_tokens"]=verify(text,tokens)
            if r["missing_tokens"]:raise ValueError("identity mismatch")
            r.update(official_original_verified=True,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name)
            if code=="sz.000820":r.update(notice_st_effective="2026-11-26",notice_limit_pct="10.00",notice_resume="2026-11-26",security_daily_reference_price_verified=False)
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_detail=str(e)[:200])
        records.append(r)
    n=sum(r["official_original_verified"] for r in records)
    return dict(asof=leads["asof"],attempted=len(records),new_originals_verified=n,total_original_issuers_verified=4+n,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("leads","pinned","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.leads.read_bytes()),json.loads(a.pinned.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_ADDITIONAL_ORIGINALS:",json.dumps(r))
