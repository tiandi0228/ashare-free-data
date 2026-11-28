"""Final six gap leads, with two official PDF targets; no promotion to PIT."""
import argparse,json,hashlib,subprocess
from pathlib import Path
from collector.p3_next_originals import safe,missing
LEADS={
"sz.000635":("2026-11-13","2026-11-24","https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12719178&stockid=000635"),
"sz.000972":("2026-11-03","2026-11-04","https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12688645&stockid=000972"),
"sz.002623":("2026-11-03","2026-11-10","https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12698478&stockid=002623"),
"sz.002827":("2026-10-26","2026-11-02","https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12686345&stockid=002827"),
"sz.000892":("2026-11-23","2026-11-24","https://epaper.cs.com.cn/zgzqb/html/2026-11/21/nw.D110000zgzqb_20261121_1-B066.htm"),
"sz.002122":("2026-11-20","2026-11-23","https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12714981&stockid=002122")}
PDFS={
"sz.000635":("https://static.cninfo.com.cn/finalpage/2026-11-20/1225680278.PDF",("000635","2026-065","2026年11月13日","2026年11月20日","继续停牌"),"HALT_EXTENSION_NOTICE"),
"sz.002827":("https://static.cninfo.com.cn/finalpage/2026-10-26/1225621271.PDF",("002827","2026-058","2026年10月26日","2026年11月2日","开始停牌"),"INITIAL_HALT_NOTICE")}
def run(queue,prior,root):
    safe(queue);safe(prior)
    if prior["total_original_issuers_verified"]!=13:raise ValueError("wrong prior count")
    by={r["issuer"]:r for r in queue["tasks"]}
    if len(by)!=19 or len(queue["tasks"])!=19:raise ValueError("wrong scope")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,(start,resume,url) in LEADS.items():
        t=by[code];days=t["vendor_nontradable_days"]
        if not days or days[0]!=start or days[-1]>=resume or t["missing_expected_sessions"]:raise ValueError("vendor interval mismatch")
        r=dict(issuer=code,public_lead_url=url,notice_start=start,notice_resume_lead=resume,vendor_days=days,extension_sha256=t["extension_sha256"],official_original_verified=False,full_interval_verified=False,first_publication_verified=False,official_certified=False)
        if code in PDFS:
            pdf,tokens,kind=PDFS[code];p=root/(code+".pdf");r.update(url=pdf,kind=kind)
            try:
                subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),pdf],check=True,capture_output=True)
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
    return dict(asof=queue["asof"],additional_public_leads=len(records),attempted=len(PDFS),new_originals_verified=n,total_original_issuers_verified=13+n,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","prior","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),json.loads(a.prior.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_FINAL_GAP_LEADS:",json.dumps(r))
