"""Extend the risk timeline using a separate official resumption original."""
import argparse,csv,hashlib,io,json,subprocess,zipfile
from pathlib import Path
from collector.p3_next_originals import safe,missing
from collector.p3_risk_timeline import reconcile
from collector.p4_curated_session_exit import sessions_between
CODE="sz.002827"
URL="https://static.cninfo.com.cn/finalpage/2026-11-02/1225650638.PDF"
TOKENS=("002827","2026-060","2026-058","2026年10月26日","2026年11月2日","开市起复牌")
START="2026-10-26"
RESUME="2026-11-02"
def verify(text):
    return not missing(text,TOKENS)
def run(queue,timeline,archive,root):
    safe(queue);safe(timeline)
    tasks={r["issuer"]:r for r in queue["tasks"]}
    prior={r["issuer"]:r for r in timeline["records"]}
    if len(tasks)!=19 or len(prior)!=19 or set(tasks)!=set(prior) or prior[CODE]["status"]!="ADDITIONAL_INTERVAL_EVIDENCE_REQUIRED":raise ValueError("wrong scope")
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=queue["source_artifact_sha256"]:raise ValueError("archive mismatch")
    t=tasks[CODE]
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError("duplicate members")
        raw=z.read(t["source_member"])
    if hashlib.sha256(raw).hexdigest()!=t["extension_sha256"]:raise ValueError("vendor SHA mismatch")
    bars=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    days=[b["date"] for b in bars if b["tradestatus"]=="0"]
    active=[b["date"] for b in bars if b["tradestatus"]=="1"]
    if days!=t["vendor_nontradable_days"] or t["missing_expected_sessions"]:raise ValueError("vendor status mismatch")
    status=reconcile(START,RESUME,days,active,sessions_between(START,queue["asof"]),queue["asof"])
    root.mkdir(parents=True,exist_ok=True);p=root/(CODE+"-resume.pdf")
    result=dict(issuer=CODE,url=URL,initial_pdf_sha256=prior[CODE]["pdf_sha256"],extension_sha256=t["extension_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False,eligible_for_trading=False)
    try:
        subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),URL],check=True,capture_output=True)
        raw=p.read_bytes()
        if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
        text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
        if not verify(text):raise ValueError("identity mismatch")
        result.update(official_original_verified=True,resume_pdf_sha256=hashlib.sha256(raw).hexdigest(),file=p.name,status=status,notice_halt_start=START,notice_resume=RESUME,vendor_days=days)
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        p.unlink(missing_ok=True);result.update(failure=type(e).__name__,failure_detail=str(e)[:200])
    counts=dict(timeline["counts"])
    if result["official_original_verified"]:
        counts["ADDITIONAL_INTERVAL_EVIDENCE_REQUIRED"]-=1
        counts[status]+=1
    return dict(asof=queue["asof"],gap_issuers=19,counts=counts,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],record=result)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","timeline","archive","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),json.loads(a.timeline.read_bytes()),a.archive,a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_INTERVAL_EXTENSION:",json.dumps(r))
