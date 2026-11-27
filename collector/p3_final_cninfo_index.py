"""Resolve exact CNINFO announcement via official index; preserve raw metadata, no PIT claim."""
import argparse,hashlib,json,re,subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode
from collector.p3_next_originals import safe,missing
API="https://www.cninfo.com.cn/new/hisAnnouncement/query"
CODE="sz.000972"
TITLE="关于法院裁定受理公司及子公司红色番茄重整及指定管理人暨公司股票交易将停牌一天并被实施退市风险警示的公告"
TOKENS=("000972","2026-073","2026年11月3日","2026年11月4日","退市风险警示","日涨跌幅限制仍为10%")
def sha(b):return hashlib.sha256(b).hexdigest()
def select(raw):
    data=json.loads(raw)
    if data.get("hasMore") is not False:raise ValueError("incomplete index")
    rows=[r for r in data["announcements"] if r.get("secCode")=="000972" and r.get("orgId")=="gssz0000972" and re.sub(r"<[^>]+>","",r.get("announcementTitle",""))==TITLE]
    if len(rows)!=1:raise ValueError("missing or ambiguous exact announcement")
    r=rows[0];path=r["adjunctUrl"]
    if not re.fullmatch(r"finalpage/2026-11-0[23]/[0-9]+\.PDF",path,re.I):raise ValueError("unexpected attachment path")
    ts=r["announcementTime"]
    if type(ts) is not int:raise ValueError("invalid timestamp")
    instant=datetime.fromtimestamp(ts/1000,timezone(timedelta(hours=8)))
    if instant.date().isoformat() not in ("2026-11-02","2026-11-03"):raise ValueError("unexpected index date")
    return r,"https://static.cninfo.com.cn/"+path,instant.isoformat()
def run(ledger,prior,root):
    safe(ledger);safe(prior)
    if prior["remaining_original_gaps"]!=[CODE] or prior["total_original_issuers_verified"]!=18:raise ValueError("wrong baseline")
    rows=[r for r in ledger["records"] if r["issuer"]==CODE]
    if len(rows)!=1 or rows[0]["vendor_nontradable_days"]!=["2026-11-03"]:raise ValueError("wrong target")
    root.mkdir(parents=True,exist_ok=True)
    meta=root/"cninfo-index.json";p=root/(CODE+".pdf")
    r=dict(issuer=CODE,extension_sha256=rows[0]["extension_sha256"],official_original_verified=False,first_publication_verified=False,full_interval_verified=False,official_certified=False)
    stage="index_download"
    try:
        payload=urlencode(dict(pageNum=1,pageSize=30,column="szse",tabName="fulltext",plate="",stock="000972,gssz0000972",searchkey="",secid="",category="",trade="",seDate="2026-11-02~2026-11-03",sortName="",sortType="",isHLtitle="false"))
        subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","30","--max-filesize","2000000","-H","Referer: https://www.cninfo.com.cn/","-H","Content-Type: application/x-www-form-urlencoded","--data",payload,"--output",str(meta),API],check=True,capture_output=True)
        stage="index_identity";raw=meta.read_bytes()
        r["index_sha256"]=sha(raw)
        row,url,stamp=select(raw)
        r.update(url=url,index_announcement_id=row["announcementId"],index_timestamp_ms=row["announcementTime"],index_timestamp_beijing=stamp,index_timestamp_semantics_verified=False)
        stage="pdf_download"
        subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","8","--max-time","25","--max-filesize","5000000","--output",str(p),url],check=True,capture_output=True)
        stage="pdf_identity";raw=p.read_bytes()
        if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
        text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=15)
        r["missing_tokens"]=missing(text.replace("％","%"),TOKENS)
        if r["missing_tokens"]:raise ValueError("identity mismatch")
        r.update(official_original_verified=True,source_sha256=sha(raw),file=p.name,notice_halt_start="2026-11-03",notice_st_effective="2026-11-04",notice_limit_pct="10.00")
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
        p.unlink(missing_ok=True);r.update(failure=type(e).__name__,failure_stage=stage,failure_detail=str(e)[:200])
    n=int(r["official_original_verified"])
    return dict(asof=ledger["asof"],total_original_issuers_verified=18+n,remaining_original_gaps=[] if n else [CODE],official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],record=r)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("ledger","prior","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.ledger.read_bytes()),json.loads(a.prior.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_FINAL_CNINFO_INDEX:",json.dumps(r))
