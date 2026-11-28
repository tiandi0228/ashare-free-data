"""Bounded official index lookup for the final two ordinary halt gaps."""
import argparse,csv,io,json,re,subprocess,zipfile
from pathlib import Path
from urllib.parse import urlencode
from collector.p3_resume_index_extension import curl,sha,stock_key
from collector.p3_next_originals import safe,missing
from collector.p3_unified_ledger import verified_pdf
from collector.p3_risk_timeline import reconcile
from collector.p4_curated_session_exit import sessions_between
TARGETS={"sh.600185":"2026-11-12","sh.600567":"2026-11-19"}
RESUME="2026-11-26"
def select(raw,code,org):
    data=json.loads(raw)
    if data.get("hasMore") is not False:raise ValueError("incomplete index")
    rows=[r for r in data["announcements"] if r.get("secCode")==code[3:] and r.get("orgId")==org and "复牌" in re.sub("<[^>]+>","",r.get("announcementTitle",""))]
    if len(rows)!=1:raise ValueError("missing or ambiguous resume notice")
    r=rows[0];p=r["adjunctUrl"]
    if not re.fullmatch(r"finalpage/2026-11-(?:25|26|27)/[0-9]+\.PDF",p,re.I) or type(r["announcementTime"]) is not int:raise ValueError("invalid attachment")
    return r,"https://static.cninfo.com.cn/"+p
def run(queue,ledger,prior,archive,root):
    for x in (queue,ledger,prior):safe(x)
    if queue["asof"]!="2026-11-25" or sha(archive.read_bytes())!=queue["source_artifact_sha256"]:raise ValueError("wrong epoch")
    tasks={r["issuer"]:r for r in queue["tasks"]};docs={r["issuer"]:r for r in ledger["records"]}
    remaining={r["issuer"]:r for r in prior["remaining_tasks"]}
    if len(tasks)!=19 or set(tasks)!=set(docs) or set(remaining)!=set(TARGETS):raise ValueError("wrong scope")
    root.mkdir(parents=True,exist_ok=True);records=[]
    with zipfile.ZipFile(archive) as z:
        for code,start in TARGETS.items():
            t=tasks[code];d=docs[code];raw=z.read(t["source_member"])
            if sha(raw)!=t["extension_sha256"] or d["extension_sha256"]!=t["extension_sha256"] or remaining[code]["extension_sha256"]!=t["extension_sha256"]:raise ValueError("provenance mismatch")
            bars=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            days=[b["date"] for b in bars if b["tradestatus"]=="0"]
            if days!=t["vendor_nontradable_days"] or any(b["code"]!=code for b in bars):raise ValueError("vendor mismatch")
            status=reconcile(start,RESUME,days,[b["date"] for b in bars if b["tradestatus"]=="1"],sessions_between(start,queue["asof"]),queue["asof"])
            r=dict(issuer=code,extension_sha256=t["extension_sha256"],initial_pdf_sha256=d["pdf_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False,resume_vendor_observed=False)
            p=root/(code+"-resume.pdf");stage="lookup"
            try:
                lookup=root/(code+"-security.json")
                curl("https://www.cninfo.com.cn/new/information/topSearch/query",lookup,("-H","Referer: https://www.cninfo.com.cn/","--data",urlencode(dict(keyWord=code[3:],maxNum=10))))
                raw=lookup.read_bytes();r["security_lookup_sha256"]=sha(raw);key=stock_key(raw,code)
                stage="index";idx=root/(code+"-index.json")
                payload=urlencode(dict(pageNum=1,pageSize=100,column="sse",tabName="fulltext",stock=key,searchkey="",plate="",category="",secid="",trade="",sortName="",sortType="",seDate="2026-11-25~2026-11-27",isHLtitle="false"))
                curl("https://www.cninfo.com.cn/new/hisAnnouncement/query",idx,("-H","Referer: https://www.cninfo.com.cn/","--data",payload))
                raw=idx.read_bytes();r["index_sha256"]=sha(raw)
                row,url=select(raw,code,key.split(",")[1]);r.update(url=url,index_announcement_id=row["announcementId"],index_timestamp_ms=row["announcementTime"],index_timestamp_semantics_verified=False)
                stage="pdf";curl(url,p);raw=p.read_bytes();verified_pdf(raw,sha(raw))
                stage="identity";txt=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
                tokens=(code[3:],"复牌","11月26日")
                if missing(txt,tokens):raise ValueError("identity mismatch")
                # Require explicit resumption date, not merely notice date.
                normalized=re.sub(r"\s+","",txt)
                if not re.search(r"11月26日.{0,40}复牌|复牌.{0,40}11月26日",normalized):raise ValueError("resume date not linked to resumption")
                r.update(official_original_verified=True,resume_pdf_sha256=sha(raw),file=p.name,status=status,notice_resume=RESUME,notice_halt_start=start)
            except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
                p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_stage=stage,failure_detail=str(e)[:200])
            records.append(r)
    remaining=[r["issuer"] for r in records if not r["official_original_verified"]]
    return dict(asof=queue["asof"],gap_issuers=19,remaining_other_interval_gaps=len(remaining),remaining_issuers=remaining,announced_resume_after_cutoff=2+2-len(remaining),official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","ledger","prior","archive","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(*[json.loads(x.read_bytes()) for x in (a.queue,a.ledger,a.prior)],a.archive,a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_FINAL_RESUME:",json.dumps(r))
