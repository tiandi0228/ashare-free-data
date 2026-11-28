"""Bounded CNINFO index discovery; candidates are not certified limit or fill evidence."""
import argparse,json,hashlib,re,subprocess
from datetime import date,timedelta
from pathlib import Path
from urllib.parse import urlencode

def sha(raw):return hashlib.sha256(raw).hexdigest()
def query(url,payload,path):
    subprocess.run(["curl","--fail","--silent","--show-error","--connect-timeout","5","--max-time","12","--max-filesize","3000000","-H","Referer: https://www.cninfo.com.cn/","--data",urlencode(payload),"--output",str(path),url],check=True,capture_output=True)
    return path.read_bytes()
def stock_key(raw,code):
    rows=[r for r in json.loads(raw) if r.get("code")==code[3:]]
    if len(rows)!=1 or not re.fullmatch(r"[A-Za-z0-9]+",rows[0].get("orgId","")):raise ValueError("ambiguous security")
    return code[3:]+","+rows[0]["orgId"]
def candidates(raw,code,org,day):
    data=json.loads(raw)
    if data.get("hasMore") is not False:raise ValueError("incomplete index")
    end=(date.fromisoformat(day)+timedelta(days=7)).isoformat()
    rows=[]
    for r in data["announcements"]:
        title=re.sub(r"<[^>]+>","",r.get("announcementTitle",""))
        if r.get("secCode")!=code[3:] or r.get("orgId")!=org or not any(k in title for k in ("异常波动","风险提示")):continue
        p=r.get("adjunctUrl","")
        if not re.fullmatch(r"finalpage/2026-[0-9]{2}-[0-9]{2}/[0-9]+\.PDF",p,re.I) or not day<=p.split("/")[1]<=end or type(r.get("announcementTime")) is not int:continue
        rows.append(dict(title=title,url="https://static.cninfo.com.cn/"+p,announcement_id=r["announcementId"],index_timestamp_ms=r["announcementTime"],index_timestamp_semantics_verified=False))
    return rows
def run(queue,root,limit=5,offset=0):
    if queue["trade_gate"]!="BLOCKED" or queue["orders"]!=[] or queue["executable_candidates"]!=[] or queue["official_limit_certified"]!=0 or queue["historical_PIT_verified"] is not False or queue["asof"]!="2026-11-25":raise ValueError("unsafe input")
    if not 1<=limit<=5 or not 0<=offset<len(queue['tasks']) or queue["remaining_notice_tasks"]!=len(queue["tasks"]):raise ValueError("bad scope")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for t in queue["tasks"][offset:offset+limit]:
        code,day=t["code"],t["day"]
        if not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",code):raise ValueError("bad code")
        prefix=code+"-"+day;end=(date.fromisoformat(day)+timedelta(days=7)).isoformat()
        r=dict(code=code,day=day,extension_sha256=t["extension_sha256"],candidates=[],official_limit_verified=False,first_publication_verified=False,fill_verified=False)
        try:
            raw=query("https://www.cninfo.com.cn/new/information/topSearch/query",dict(keyWord=code[3:],maxNum=10),root/(prefix+"-security.json"))
            r["security_lookup_sha256"]=sha(raw);key=stock_key(raw,code)
            raw=query("https://www.cninfo.com.cn/new/hisAnnouncement/query",dict(pageNum=1,pageSize=100,column="sse" if code.startswith("sh.") else "szse",tabName="fulltext",stock=key,searchkey="",plate="",category="",secid="",trade="",sortName="",sortType="",seDate=day+"~"+end,isHLtitle="false"),root/(prefix+"-index.json"))
            r["index_sha256"]=sha(raw);r["candidates"]=candidates(raw,code,key.split(",")[1],day)
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:r.update(failure=type(e).__name__,failure_detail=str(e)[:200])
        records.append(r)
    return dict(asof=queue["asof"],attempted=len(records),tasks_with_index_candidates=sum(bool(r["candidates"]) for r in records),original_notice_leads_added=0,official_limit_certified=0,historical_PIT_verified=False,execution_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--queue",type=Path,required=True);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--offset",type=int,default=0);a=p.parse_args()
    r=run(json.loads(a.queue.read_bytes()),a.root,offset=a.offset);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_INDEX_DISCOVERY:",json.dumps(r))
