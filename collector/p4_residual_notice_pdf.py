"""Verify bounded official PDF leads against explicit event dates; never certify fills."""
import argparse,hashlib,json,re,subprocess
from datetime import date,timedelta
from pathlib import Path

def event_date_matches(text,day):
    d=date.fromisoformat(day)
    s=re.sub(r"\s+","",text)
    # Require a date in the same sentence as a trading abnormality or price deviation.
    token=rf"(?:{d.year}年)?0?{d.month}月0?{d.day}日"
    return any(re.search(token,part) and re.search(r"交易|涨幅|跌幅|偏离值|收盘",part) for part in re.split(r"[。；;]",s))
def verify(text,code,day):
    s=re.sub(r"\s+","",text)
    return code[3:] in s and "异常波动" in s and event_date_matches(text,day)
def run(discovery,queue,root):
    for r in (discovery,queue):
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["official_limit_certified"]!=0 or r["historical_PIT_verified"] is not False:raise ValueError("unsafe input")
    if discovery["asof"]!=queue["asof"] or discovery["asof"]!="2026-11-25":raise ValueError("epoch mismatch")
    tasks={(r["code"],r["day"]):r for r in queue["tasks"]};records=[];seen=set()
    if len(discovery["records"])>5:raise ValueError("excess scope")
    root.mkdir(parents=True,exist_ok=True)
    for r in discovery["records"]:
        code,day=r["code"],r["day"];key=(code,day)
        if key in seen or key not in tasks or tasks[key]["extension_sha256"]!=r["extension_sha256"]:raise ValueError("scope mismatch")
        seen.add(key)
        out=dict(code=code,day=day,extension_sha256=r["extension_sha256"],original_notice_verified=False,official_limit_verified=False,first_publication_verified=False,fill_verified=False,attempts=[])
        for c in r["candidates"][:3]:
            url=c["url"];m=re.fullmatch(r"https://static\.cninfo\.com\.cn/finalpage/(2026-\d{2}-\d{2})/(\d+)\.PDF",url)
            if not m or m[2]!=str(c["announcement_id"]) or not day<=m[1]<=(date.fromisoformat(day)+timedelta(days=7)).isoformat():raise ValueError("invalid source")
            p=root/(code+"-"+day+"-"+m[2]+".pdf");a=dict(url=url)
            try:
                subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","5","--max-time","12","--max-filesize","5000000","--output",str(p),url],check=True,capture_output=True)
                raw=p.read_bytes()
                if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
                a["source_sha256"]=hashlib.sha256(raw).hexdigest()
                txt=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
                if not verify(txt,code,day):raise ValueError("event date or identity not established")
                out.update(original_notice_verified=True,source_sha256=a["source_sha256"],url=url,file=p.name,evidence_type="RETROSPECTIVE_EVENT_DATE_NOTICE")
                a["verified"]=True
            except (OSError,ValueError,subprocess.SubprocessError) as e:
                a.update(verified=False,failure=str(e)[:200])
            out["attempts"].append(a)
            if out["original_notice_verified"]:break
        records.append(out)
    return dict(asof=queue["asof"],attempted=len(records),original_notice_leads_added=sum(r["original_notice_verified"] for r in records),official_limit_certified=0,historical_PIT_verified=False,execution_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("discovery","queue","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.discovery.read_bytes()),json.loads(a.queue.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_RESIDUAL_PDF:",json.dumps(r))
