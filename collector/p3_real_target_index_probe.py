"""Bounded CNINFO announcement discovery for real archived P1 mainboard issuers.

The API is a discovery index, NOT independent proof of first publication,
notice completeness or historical trading eligibility. Search only three
pages per issuer; no results never mean the issuer was safe.
"""
import argparse,json,re
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
ENDPOINT="https://www.cninfo.com.cn/new/hisAnnouncement/query"
CODE_RE=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}\Z")
PDF_RE=re.compile(r"finalpage/\d{4}-\d{2}-\d{2}/\d+\.PDF\Z",re.I)
MAX_PAGES=3
PAGE_SIZE=30

def select_targets(queue,limit=3):
    if queue.get("phase")!="P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE" or queue.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid research queue")
    codes=[]
    for row in queue["targets"]:
        issuer=row["issuer"]
        if not CODE_RE.fullmatch(issuer):raise ValueError("invalid mainboard issuer")
        if issuer not in codes:codes.append(issuer)
        if len(codes)==limit:break
    return codes

def _post_query(params):
    req=Request(ENDPOINT,data=urlencode(params).encode(),headers={
        "User-Agent":"Mozilla/5.0","Referer":"https://www.cninfo.com.cn/",
        "X-Requested-With":"XMLHttpRequest",
        "Content-Type":"application/x-www-form-urlencoded"},method="POST")
    with urlopen(req,timeout=18) as response:
        if response.geturl()!=ENDPOINT:raise ValueError("unexpected index redirect")
        raw=response.read(1500001)
    if len(raw)>1500000:raise ValueError("oversized index response")
    return json.loads(raw)

def query(issuer,fetch_page=None,max_pages=MAX_PAGES,observed_dates=None):
    if not isinstance(issuer,str) or not CODE_RE.fullmatch(issuer):
        raise ValueError("not a mainboard issuer")
    if type(max_pages)!=int or not 1<=max_pages<=MAX_PAGES:
        raise ValueError("unbounded page request")
    fetch_page=fetch_page or _post_query
    code=issuer[-6:]
    column="sse" if issuer.startswith("sh.") else "szse"
    today=datetime.now(ZoneInfo("Asia/Shanghai")).date()
    start=date.fromisoformat("2024-10-20")
    end=today
    if observed_dates is not None:
        if (not isinstance(observed_dates,list) or not 1<=len(observed_dates)<=3
            or observed_dates!=sorted(set(observed_dates))):
            raise ValueError("invalid bounded vendor suspension dates")
        dates=[date.fromisoformat(x) for x in observed_dates]
        if any(x>today for x in dates):raise ValueError("future vendor suspension")
        # A narrow historical source-search window, not proof of the
        # notice's first publication or effective date.
        start=min(dates)-timedelta(days=45)
        end=min(today,max(dates)+timedelta(days=7))
    window=start.isoformat()+"~"+end.isoformat()
    found=[];seen=set()
    for page in range(1,max_pages+1):
        params={"pageNum":page,"pageSize":PAGE_SIZE,"tabName":"fulltext",
                "column":column,"plate":"sh" if column=="sse" else "sz",
                "stock":"","searchkey":code,"category":"","sortName":"",
                "sortType":"","seDate":window}
        data=fetch_page(params)
        if not isinstance(data,dict) or not isinstance(data.get("announcements"),list):
            raise ValueError("index missing announcements, not proof of no notices")
        entries=data["announcements"]
        if len(entries)>PAGE_SIZE:raise ValueError("unbounded index response")
        for e in entries:
            if not isinstance(e,dict) or str(e.get("secCode",""))!=code:
                continue
            path=e.get("adjunctUrl","")
            if not isinstance(path,str) or not PDF_RE.fullmatch(path):
                continue
            notice_id=str(e.get("announcementId",""))
            if path.rsplit("/",1)[-1].split(".",1)[0]!=notice_id:
                continue
            if notice_id in seen:continue
            seen.add(notice_id)
            found.append({"announcement_id":notice_id,
                          "official_pdf_url":"https://static.cninfo.com.cn/"+path,
                          "index_published_milliseconds_unverified":e.get("announcementTime"),
                          "announcement_title_unverified":str(e.get("announcementTitle",""))[:200],
                          "index_page_observed":page,
                          "original_bytes_captured":False,
                          "historical_PIT_verified":False})
        # The index may change while paginating. Missing results are never
        # sufficient evidence that a notice or a historical risk did not exist.
        if len(entries)<PAGE_SIZE or data.get("hasMore") is False:break
    return found

def run(queue,client=query):
    codes=select_targets(queue)
    results=[]
    for issuer in codes:
        try:
            target=next((t for t in queue["targets"] if t["issuer"]==issuer),{})
            transition=target.get("vendor_halt_transition_research_days") or []
            vendor_nontrading=target.get("vendor_suspended_research_days") or []
            if transition:
                candidates=client(issuer,observed_dates=transition[-3:])
            elif vendor_nontrading:
                candidates=client(issuer,observed_dates=vendor_nontrading[-3:])
            else:
                candidates=client(issuer)
            if not isinstance(candidates,list) or len(candidates)>MAX_PAGES*PAGE_SIZE:
                raise ValueError("invalid or oversized client candidates")
            results.append({"issuer":issuer,
                "status":"INDEX_CANDIDATES_UNVERIFIED" if candidates else "NO_INDEX_MATCH_NOT_NO_RISK",
                "historical_vendor_event_window_used":bool(transition or vendor_nontrading),
                "historical_vendor_transition_days":transition[-3:],
                "candidates":candidates})
        except Exception as e:
            results.append({"issuer":issuer,"status":"INDEX_UNAVAILABLE_NOT_NO_RISK",
                            "error_type":type(e).__name__,"candidates":[]})
    return {"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY","attempted":len(results),
            "max_page_budget_per_issuer":MAX_PAGES,
            "index_exhaustive_or_historical_asof_proof":False,
            "results":results,"historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=run(json.loads(Path(a.queue).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"phase":result["phase"],"attempted":result["attempted"],
                      "max_page_budget_per_issuer":MAX_PAGES,
                      "states":[x["status"] for x in result["results"]]}))
if __name__=="__main__":main()
