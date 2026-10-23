"""Bounded no-cost CNINFO announcement index probe, never PIT certification."""
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ENDPOINT="https://www.cninfo.com.cn/new/hisAnnouncement/query"
def normalize(payload, expected_id):
    if not isinstance(payload,dict):raise ValueError("index JSON not an object")
    entries=payload.get("announcements")
    if not isinstance(entries,list):
        if "totalAnnouncement" in payload and payload.get("announcements") is None and payload["totalAnnouncement"]==0:
            return []
        raise ValueError("missing announcements list")
    matches=[]
    for x in entries:
        if str(x.get("announcementId"))!=expected_id:continue
        code=str(x.get("secCode",""))
        adjunct=x.get("adjunctUrl","")
        if not re.fullmatch(r"\d{6}",code) or not isinstance(adjunct,str) or not re.fullmatch(r"finalpage/\d{4}-\d{2}-\d{2}/\d+\.PDF",adjunct,re.I):
            raise ValueError("invalid index identity")
        if adjunct.split("/")[-1].split(".")[0]!=expected_id:raise ValueError("index URL/ID mismatch")
        matches.append({"announcement_id":expected_id,
                        "issuer":("sh." if code.startswith("6") else "sz.")+code,
                        "original_url":"https://static.cninfo.com.cn/"+adjunct,
                        "published_at":x.get("announcementTime"),
                        "timestamp_type":"UNAUTHENTICATED_INDEX_MILLISECONDS",
                        "original_index_source":ENDPOINT})
    if len(matches)>1:raise ValueError("duplicate announcement ID")
    return matches
def fetch_one(entry):
    url=entry["url"]; match=re.search(r"/(\d+)\.PDF$",url,re.I)
    if not match:raise ValueError("invalid PDF URL")
    identifier=match.group(1)
    code=entry["issuer"][-6:]
    day=url.split("/finalpage/")[1][:10]
    data=urlencode({"pageNum":1,"pageSize":30,"tabName":"fulltext","searchkey":code,
                    "seDate":day+"~"+day}).encode()
    req=Request(ENDPOINT,data=data,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.cninfo.com.cn/","Content-Type":"application/x-www-form-urlencoded"},method="POST")
    with urlopen(req,timeout=18) as response:
        if response.geturl()!=ENDPOINT:raise ValueError("unexpected index redirect")
        content=response.read(2000001)
    if len(content)>2000000:raise ValueError("index response too large")
    payload=json.loads(content)
    try:
        return normalize(payload,identifier)
    except ValueError as exc:
        if "missing announcements list" not in str(exc):raise
        # Save schema-only diagnostics, never silently treat a malformed payload as an empty page.
        shape={"response_keys":sorted(str(k)[:60] for k in payload) if isinstance(payload,dict) else [],
               "totalAnnouncement":payload.get("totalAnnouncement") if isinstance(payload,dict) else None,
               "has_announcements":isinstance(payload.get("announcements"),list) if isinstance(payload,dict) else False}
        raise ValueError("INDEX_RESPONSE_SCHEMA:"+json.dumps(shape,ensure_ascii=False)) from exc
def probe(manifest):
    out=[];errors=[]
    for entry in manifest:
        try:
            found=fetch_one(entry)
            if found:out.extend(found)
            else:errors.append({"source_id":entry["id"],"failure_type":"INDEX_RECORD_NOT_FOUND"})
        except Exception as ex:errors.append({"source_id":entry["id"],"failure_type":type(ex).__name__,"failure_detail":str(ex)[:180]})
    return {"phase":"P3_CNINFO_LIVE_INDEX_PROBE","requested":len(manifest),"linked_index_rows":out,
            "index_records_found":len(out),"unavailable_or_unmatched":errors,
            "first_publication_verified":False,"historical_PIT_eligible":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--out",required=True)
    x=p.parse_args();report=probe(json.loads(Path(x.manifest).read_text()))
    Path(x.out).parent.mkdir(parents=True,exist_ok=True)
    Path(x.out).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="linked_index_rows"},ensure_ascii=False))
if __name__=="__main__":main()
