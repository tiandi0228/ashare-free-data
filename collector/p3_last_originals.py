"""Resolve remaining original gaps without promoting publication timing or execution."""
import argparse,json,hashlib,subprocess
from pathlib import Path
from collector.p3_next_originals import safe,missing
SOURCES={
"sz.000892":("https://static.cninfo.com.cn/finalpage/2026-11-21/1225682608.PDF",("000892","2026-057","实施其他风险警示","2026年11月23日","2026年11月24日","仍为10%"),"2026-11-23","2026-11-24","ADD_ST"),
"sz.002623":("https://static.cninfo.com.cn/finalpage/2026-11-10/1225664631.PDF",("002623","2026-062","2026-059","2026-061","2026年11月3日","2026年11月5日","2026年11月10日","复牌"),"2026-11-03","2026-11-10","RESUME"),
"sz.002122":("https://static.cninfo.com.cn/finalpage/2026-11-20/1225679977.PDF",("002122","2026-051","撤销其他风险警示","2026年11月20日","2026年11月23日","仍为10%"),"2026-11-20","2026-11-23","REMOVE_ST")}
def run(ledger,root):
    safe(ledger)
    by={r["issuer"]:r for r in ledger["records"]}
    if len(by)!=19 or len(ledger["records"])!=19 or ledger["original_issuers_verified"]!=15:raise ValueError("wrong scope")
    gaps=set(ledger["remaining_original_gaps"])
    if gaps!=set(SOURCES)|{"sz.000972"}:raise ValueError("wrong remaining scope")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,(url,tokens,start,resume,kind) in SOURCES.items():
        t=by[code]
        if t["official_original_verified"] is not False or t["notice_start"]!=start or t["notice_resume_lead"]!=resume:raise ValueError("wrong target")
        p=root/(code+".pdf");r=dict(issuer=code,url=url,kind=kind,extension_sha256=t["extension_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False)
        try:
            subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),url],check=True,capture_output=True)
            raw=p.read_bytes()
            if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
            r["missing_tokens"]=missing(text.replace("％","%"),tokens)
            if r["missing_tokens"]:raise ValueError("identity mismatch")
            r.update(official_original_verified=True,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name,notice_halt_start=start,notice_resume=resume)
            if kind!="RESUME":r.update(notice_st_effective=resume,notice_limit_pct="10.00",security_daily_reference_price_verified=False)
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_detail=str(e)[:200])
        records.append(r)
    accepted={r["issuer"] for r in records if r["official_original_verified"]}
    return dict(asof=ledger["asof"],attempted=len(records),new_originals_verified=len(accepted),total_original_issuers_verified=15+len(accepted),remaining_original_gaps=sorted(gaps-accepted),official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("ledger","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.ledger.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_LAST_ORIGINALS:",json.dumps(r))
