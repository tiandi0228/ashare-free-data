"""Retrospective interval and ST transition evidence, never a PIT assertion."""
import argparse,json,hashlib,re,subprocess,csv,io,zipfile
from pathlib import Path
from datetime import date,timedelta
from collector.p3_next_originals import safe,missing
from collector.p3_unified_ledger import verified_pdf
from collector.p4_curated_session_exit import sessions_between
# Explicitly scoped facts transcribed from already accepted originals.
INTERVALS={
"sh.601326":("2026-10-21","2026-11-04",("2026年10月21日","2026年11月4日","公司股票复牌")),
"sz.000831":("2026-11-02","2026-11-16",("2026年11月2日","2026年11月16日","公司股票复牌")),
"sz.002129":("2026-11-02","2026-11-16",("2026年11月2日","2026年11月16日","公司股票复牌")),
"sz.002623":("2026-11-03","2026-11-10",("2026年11月3日","2026年11月10日","复牌")),
"sh.605255":("2026-11-16","2026-11-19",("2026年11月16日","2026/11/18","2026/11/19","停牌核查结果")),
"sh.603580":("2026-11-23","2026-11-24",("2026/11/23","2026/11/24","停牌一个交易日")),
"sz.002872":("2026-11-23","2026-11-24",("2026年11月23日","2026年11月24日","撤销其他风险警示")),
"sz.000892":("2026-11-23","2026-11-24",("2026年11月23日","2026年11月24日","实施其他风险警示")),
"sz.002122":("2026-11-20","2026-11-23",("2026年11月20日","2026年11月23日","撤销其他风险警示")),
"sz.000972":("2026-11-03","2026-11-04",("2026年11月3日","2026年11月4日","退市风险警示")),
"sh.603595":("2026-11-25","2026-11-26",("11月25日","11月26日","撤销其他风险警示")),
"sz.000820":("2026-11-25","2026-11-26",("2026年11月25日","2026年11月26日","实施其他风险警示")),
}
ST={
"sz.002872":("2026-11-24","REMOVE_OTHER_RISK_WARNING",("撤销其他风险警示","日涨跌幅限制仍为10%")),
"sz.000892":("2026-11-24","ADD_OTHER_RISK_WARNING",("实施其他风险警示","仍为10%")),
"sz.002122":("2026-11-23","REMOVE_OTHER_RISK_WARNING",("撤销其他风险警示","仍为10%")),
"sz.000972":("2026-11-04","ADD_DELISTING_RISK_WARNING",("退市风险警示","日涨跌幅限制仍为10%")),
"sz.000820":("2026-11-26","ADD_OTHER_RISK_WARNING",("实施其他风险警示","涨跌幅限制不变","10%")),
"sh.603595":("2026-11-26","REMOVE_OTHER_RISK_WARNING",("撤销其他风险警示",)),
}
def reconcile(start,resume,vendor_days,active_days,calendar,cutoff):
    if not start<resume:raise ValueError("invalid interval")
    expected=[d for d in calendar if start<=d<resume and d<=cutoff]
    if not expected or expected!=vendor_days:raise ValueError("interval mismatch")
    if resume>cutoff:return "ANNOUNCED_RESUME_AFTER_CUTOFF"
    if resume not in active_days:raise ValueError("resume not observed")
    return "RETROSPECTIVE_INTERVAL_MATCH"
def run(queue,ledger,root,archive):
    safe(queue);safe(ledger)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=queue["source_artifact_sha256"]:raise ValueError("vendor archive mismatch")
    tasks={r["issuer"]:r for r in queue["tasks"]};docs={r["issuer"]:r for r in ledger["records"]}
    if len(tasks)!=19 or len(docs)!=19 or set(tasks)!=set(docs) or ledger["original_issuers_verified"]!=19:raise ValueError("wrong scope")
    cutoff=queue["asof"];calendar=[str(d) for d in sessions_between("2026-10-21",cutoff)]
    records=[]
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError("duplicate members")
        for code,t in sorted(tasks.items()):
            d=docs[code]
            if d["extension_sha256"]!=t["extension_sha256"] or d["official_original_verified"] is not True:raise ValueError("provenance")
            p=root/(code+".pdf");raw=p.read_bytes();verified_pdf(raw,d["pdf_sha256"])
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=30).replace("％","%")
            csvraw=z.read(t["source_member"])
            if hashlib.sha256(csvraw).hexdigest()!=t["extension_sha256"]:raise ValueError("vendor SHA mismatch")
            bars=list(csv.DictReader(io.StringIO(csvraw.decode("utf-8-sig"))))
            active=[b["date"] for b in bars if b["tradestatus"]=="1"]
            if [b["date"] for b in bars if b["tradestatus"]=="0"]!=t["vendor_nontradable_days"]:raise ValueError("vendor status mismatch")
            r=dict(issuer=code,pdf_sha256=d["pdf_sha256"],extension_sha256=t["extension_sha256"],status="ADDITIONAL_INTERVAL_EVIDENCE_REQUIRED",first_publication_verified=False,full_interval_verified=False,official_certified=False,eligible_for_trading=False)
            if code in INTERVALS:
                start,resume,tokens=INTERVALS[code]
                if missing(text,tokens):raise ValueError("interval text mismatch "+code)
                r.update(status=reconcile(start,resume,t["vendor_nontradable_days"],active,calendar,cutoff),notice_halt_start=start,notice_resume=resume)
            if code in ST:
                effective,kind,tokens=ST[code]
                if missing(text,tokens):raise ValueError("ST text mismatch "+code)
                r.update(st_transition=kind,st_effective_date=effective,st_transition_notice_supported=True,st_history_complete=False,security_daily_reference_price_verified=False)
            records.append(r)
    from collections import Counter
    return dict(asof=cutoff,gap_issuers=19,counts=dict(Counter(r["status"] for r in records)),st_transition_notice_supported=sum(r.get("st_transition_notice_supported",False) for r in records),official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","ledger","root","archive","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),json.loads(a.ledger.read_bytes()),a.root,a.archive);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_RISK_TIMELINE:",json.dumps({k:v for k,v in r.items() if k!="records"}))
