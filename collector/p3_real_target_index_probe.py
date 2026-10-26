"""Bounded live CNINFO index lookup for actual missing P1 issuers; no PIT promotion."""
import argparse,json,re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ENDPOINT="https://www.cninfo.com.cn/new/hisAnnouncement/query"

def select_targets(queue,limit=3):
    if queue.get("phase")!="P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE" or queue.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid research queue")
    codes=[]
    for row in queue["targets"]:
        issuer=row["issuer"]
        if not re.fullmatch(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}",issuer):
            raise ValueError("invalid mainboard issuer")
        if issuer not in codes:codes.append(issuer)
        if len(codes)==limit:break
    return codes

def query(issuer):
    code=issuer[-6:]
    params={"pageNum":1,"pageSize":30,"tabName":"fulltext","searchkey":code,
            "seDate":"2025-01-01~2026-10-26","plate":"sh" if issuer.startswith("sh.") else "sz"}
    req=Request(ENDPOINT,data=urlencode(params).encode(),headers={"User-Agent":"Mozilla/5.0",
            "Referer":"https://www.cninfo.com.cn/","Content-Type":"application/x-www-form-urlencoded"},method="POST")
    with urlopen(req,timeout=18) as r:
        if r.geturl()!=ENDPOINT:raise ValueError("unexpected redirected announcement index")
        raw=r.read(1500001)
    if len(raw)>1500000:raise ValueError("oversize index payload")
    data=json.loads(raw)
    entries=data.get("announcements")
    if not isinstance(entries,list):raise ValueError("missing index results: not evidence of no notices")
    found=[]
    for e in entries:
        if str(e.get("secCode",""))!=code:continue
        path=e.get("adjunctUrl","")
        if not isinstance(path,str) or not re.fullmatch(r"finalpage/\d{4}-\d{2}-\d{2}/\d+\.PDF",path,re.I):continue
        found.append({"announcement_id":str(e.get("announcementId","")),
                      "official_pdf_url":"https://static.cninfo.com.cn/"+path,
                      "index_published_milliseconds_unverified":e.get("announcementTime"),
                      "original_bytes_captured":False,"historical_PIT_verified":False})
    return found

def run(queue,client=query):
    codes=select_targets(queue)
    results=[]
    for issuer in codes:
        try:
            candidates=client(issuer)
            results.append({"issuer":issuer,"status":"INDEX_CANDIDATES_UNVERIFIED" if candidates else "NO_INDEX_MATCH_NOT_NO_RISK","candidates":candidates})
        except Exception as e:
            results.append({"issuer":issuer,"status":"INDEX_UNAVAILABLE_NOT_NO_RISK","error_type":type(e).__name__,"candidates":[]})
    return {"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY","attempted":len(results),"results":results,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=run(json.loads(Path(a.queue).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({"phase":r["phase"],"attempted":r["attempted"],"states":[x["status"] for x in r["results"]]}))
if __name__=="__main__":main()
