"""Resolve two resumption notices via official index and replay frozen vendor intervals."""
import argparse,csv,hashlib,io,json,re,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlencode
from collector.p3_next_originals import safe,missing
from collector.p3_risk_timeline import reconcile
from collector.p4_curated_session_exit import sessions_between
from collector.p3_unified_ledger import verified_pdf
SOURCES={
"sh.605258":("sse","2026-10-30","2026-11-02","关于控股股东筹划控制权变更事项进展暨股票复牌的公告","2026-10-26","2026-11-02",("605258","2026-021","2026-022","2026年10月26日","2026年11月2日","复牌")),
"sz.000635":("szse","2026-11-23","2026-11-24","关于披露《发行股份购买资产暨关联交易预案》的一般风险提示暨公司股票复牌的公告","2026-11-13","2026-11-24",("000635","2026-063","2026年11月13日","2026年11月24日","复牌"))}
def sha(b):return hashlib.sha256(b).hexdigest()
def select(raw,code,title,lo,hi):
    data=json.loads(raw)
    if data.get("hasMore") is not False:raise ValueError("incomplete index")
    announcements=data.get("announcements")
    if not isinstance(announcements,list):raise ValueError("empty or invalid announcement index")
    rows=[r for r in announcements if r.get("secCode")==code[3:] and re.sub(r"\s+","",re.sub(r"<[^>]+>","",r.get("announcementTitle",""))).split("：")[-1]==title]
    if len(rows)!=1:raise ValueError("missing or ambiguous notice")
    r=rows[0];p=r["adjunctUrl"]
    if not re.fullmatch(r"finalpage/2026-[0-9]{2}-[0-9]{2}/[0-9]+\.PDF",p,re.I) or not lo<=p.split("/")[1]<=hi:raise ValueError("invalid attachment")
    if type(r["announcementTime"]) is not int:raise ValueError("invalid timestamp")
    return r,"https://static.cninfo.com.cn/"+p
def stock_key(raw,code):
    data=json.loads(raw)
    if not isinstance(data,list):raise ValueError("invalid security lookup")
    rows=[r for r in data if r.get("code")==code[3:]]
    if len(rows)!=1:raise ValueError("missing or ambiguous security lookup")
    org=rows[0].get("orgId")
    if not isinstance(org,str) or not re.fullmatch(r"[A-Za-z0-9]+",org):raise ValueError("invalid organization ID")
    return code[3:]+","+org
def curl(url,p,extra=()):
    subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","30","--max-filesize","5000000",*extra,"--output",str(p),url],check=True,capture_output=True)
def run(queue,timeline,prior,archive,root):
    for r in (queue,timeline,prior):safe(r)
    if prior["record"]["official_original_verified"] is not True or prior["counts"]["RETROSPECTIVE_INTERVAL_MATCH"]!=11:raise ValueError("wrong prior")
    if sha(archive.read_bytes())!=queue["source_artifact_sha256"]:raise ValueError("archive mismatch")
    tasks={r["issuer"]:r for r in queue["tasks"]};docs={r["issuer"]:r for r in timeline["records"]}
    if len(tasks)!=19 or set(tasks)!=set(docs):raise ValueError("wrong scope")
    root.mkdir(parents=True,exist_ok=True);records=[];counts=dict(prior["counts"])
    with zipfile.ZipFile(archive) as z:
        for code,(column,lo,hi,title,start,resume,tokens) in SOURCES.items():
            t=tasks[code]
            if docs[code]["status"]!="ADDITIONAL_INTERVAL_EVIDENCE_REQUIRED":raise ValueError("wrong target")
            raw=z.read(t["source_member"])
            if sha(raw)!=t["extension_sha256"]:raise ValueError("CSV mismatch")
            bars=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            days=[b["date"] for b in bars if b["tradestatus"]=="0"]
            if days!=t["vendor_nontradable_days"]:raise ValueError("status mismatch")
            status=reconcile(start,resume,days,[b["date"] for b in bars if b["tradestatus"]=="1"],sessions_between(start,queue["asof"]),queue["asof"])
            meta=root/(code+"-index.json");p=root/(code+"-resume.pdf")
            r=dict(issuer=code,extension_sha256=t["extension_sha256"],initial_pdf_sha256=docs[code]["pdf_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False)
            stage="index"
            try:
                lookup=root/(code+"-security.json")
                curl("https://www.cninfo.com.cn/new/information/topSearch/query",lookup,("-H","Referer: https://www.cninfo.com.cn/","--data",urlencode(dict(keyWord=code[3:],maxNum=10))))
                lookup_raw=lookup.read_bytes();r["security_lookup_sha256"]=sha(lookup_raw)
                key=stock_key(lookup_raw,code);r["security_key"]=key
                payload=urlencode(dict(pageNum=1,pageSize=100,column=column,tabName="fulltext",stock=key,searchkey="",plate="",category="",secid="",trade="",sortName="",sortType="",seDate=lo+"~"+hi,isHLtitle="false"))
                curl("https://www.cninfo.com.cn/new/hisAnnouncement/query",meta,("-H","Referer: https://www.cninfo.com.cn/","--data",payload))
                raw=meta.read_bytes();r["index_sha256"]=sha(raw)
                data=json.loads(raw);r["index_titles"]=[x.get("announcementTitle") for x in (data.get("announcements") or []) if x.get("secCode")==code[3:]]
                row,url=select(raw,code,title,lo,hi)
                if row.get("orgId")!=key.split(",")[1]:raise ValueError("organization mismatch")
                r.update(url=url,index_announcement_id=row["announcementId"],index_timestamp_ms=row["announcementTime"],index_timestamp_semantics_verified=False)
                stage="pdf";curl(url,p);raw=p.read_bytes();verified_pdf(raw,sha(raw))
                stage="identity";text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
                r["missing_tokens"]=missing(text,tokens)
                if r["missing_tokens"]:raise ValueError("identity mismatch")
                r.update(official_original_verified=True,resume_pdf_sha256=sha(raw),file=p.name,status=status,notice_halt_start=start,notice_resume=resume)
                counts["ADDITIONAL_INTERVAL_EVIDENCE_REQUIRED"]-=1;counts[status]+=1
            except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
                p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_stage=stage,failure_detail=str(e)[:200])
            records.append(r)
    return dict(asof=queue["asof"],gap_issuers=19,counts=counts,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","timeline","prior","archive","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(*[json.loads(x.read_bytes()) for x in (a.queue,a.timeline,a.prior)],a.archive,a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_RESUME_INDEX_EXTENSION:",json.dumps(r))
