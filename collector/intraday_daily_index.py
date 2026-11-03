"""Rebuild a date-index from immutable five-stock research snapshots. NO TRADES.

Index is a convenient pointer, not a certified PIT source or execution feed.
All entries are regenerated from the remote archive branch, never from a
runner-local cache. No brokerage actions or trading signals are implemented.
"""
import argparse,base64,datetime as dt,hashlib,json,os,re
from pathlib import Path
from collector.intraday_snapshot_archive import api,validate,BRANCH,WATCHLIST,REPO_RE
from collector.intraday_source_health import source_health

DAY=re.compile(r"20\d{2}-\d{2}-\d{2}\Z")
ENTRY=re.compile(r"run_([1-9]\d*)_attempt_([1-9]\d*)\.json\Z")

def build(repo,day):
    if not isinstance(repo,str) or not REPO_RE.fullmatch(repo):
        raise ValueError("invalid repository")
    if not isinstance(day,str) or not DAY.fullmatch(day):
        raise ValueError("invalid archive day")
    if dt.date.fromisoformat(day).isoformat()!=day:
        raise ValueError("invalid calendar day")
    folder=f"snapshots/{day}"
    files=api(repo,f"contents/{folder}?ref={BRANCH}")
    if not isinstance(files,list) or not 1<=len(files)<=80:
        raise ValueError("missing or oversized daily archive folder")
    rows=[]
    seen=set()
    for item in files:
        if not isinstance(item,dict) or item.get("type")!="file":
            raise ValueError("unexpected archive directory entry")
        name=item.get("name","")
        m=ENTRY.fullmatch(name)
        path=f"{folder}/{name}"
        if not m or item.get("path")!=path:
            raise ValueError("unrecognized daily archive file")
        run_id,attempt=map(int,m.groups())
        if (run_id,attempt) in seen: raise ValueError("duplicate run identity")
        seen.add((run_id,attempt))
        saved=api(repo,f"contents/{path}?ref={BRANCH}")
        if not isinstance(saved,dict) or saved.get("path")!=path or not saved.get("sha"):
            raise ValueError("missing remote snapshot readback")
        raw=base64.b64decode(saved.get("content",""))
        validated_path,snapshot=validate(raw,run_id,attempt)
        if validated_path!=path or saved["sha"]!=item.get("sha"):
            raise ValueError("remote snapshot identity changed")
        summary={}
        for code in sorted(WATCHLIST):
            row=snapshot["symbols"][code]
            quote=row.get("quote",{})
            validation=row.get("validation",{})
            if row.get("status")=="SOURCE_UNAVAILABLE":
                status="SOURCE_UNAVAILABLE"
                issues=["SOURCE_UNAVAILABLE"]
            else:
                status=validation.get("status","RESEARCH_ONLY")
                if status!="RESEARCH_ONLY":
                    raise ValueError("nonresearch snapshot status")
                issues=validation.get("validation_issues")
                if not isinstance(issues,list) or any(not isinstance(x,str) for x in issues):
                    raise ValueError("invalid quality issue list")
            summary[code]={
                "status":status,
                "error_stage":row.get("error_stage") if status=="SOURCE_UNAVAILABLE" else None,
                "error_type":row.get("error_type") if status=="SOURCE_UNAVAILABLE" else None,
                "quote_time":quote.get("quote_time"),
                "observed_price_cny":quote.get("price"),
                "reported_volume_ratio":quote.get("volume_ratio"),
                "minute_rows_today":row.get("minute",{}).get("rows_today"),
                "quality_issues":issues,
                "executable_quote":False,
            }
        rows.append({"run_id":run_id,"run_attempt":attempt,
                     "asof":snapshot["asof"],"path":path,
                     "sha256":hashlib.sha256(raw).hexdigest(),
                     "symbols":summary})
    rows.sort(key=lambda x:(x["run_id"],x["run_attempt"]))
    latest=rows[-1]
    return {
        "phase":"P1_READ_ONLY_DAILY_SNAPSHOT_INDEX",
        "date":day,"source_branch":BRANCH,"entries_count":len(rows),
        "entries":rows,"latest_run":latest["run_id"],
        "latest_by_symbol":latest["symbols"],
        "source_reliability_sample":source_health(rows),
        "index_is_not_live_quote":True,
        "minute_data_complete_certified":False,
        "cross_source_price_certified":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def persist(repo,index):
    day=index["date"]
    path=f"indexes/{day}.json"
    raw=(json.dumps(index,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    if len(raw)>500000:raise ValueError("oversized index")
    endpoint=f"contents/{path}?ref={BRANCH}"
    existing=api(repo,endpoint)
    if existing is not None:
        if not isinstance(existing,dict) or existing.get("path")!=path:
            raise ValueError("invalid index pointer")
        previous=base64.b64decode(existing.get("content",""))
        if previous==raw:
            return {"status":"UNCHANGED","path":path,"trade_gate":"BLOCKED"}
    payload={
        "message":"index(p1): rebuild daily five-stock research snapshot index [NO TRADES]",
        "branch":BRANCH,
        "content":base64.b64encode(raw).decode(),
    }
    if existing is not None:
        if not existing.get("sha"):raise ValueError("index update SHA missing")
        payload["sha"]=existing["sha"]
    api(repo,f"contents/{path}",method="PUT",data=payload)
    readback=api(repo,endpoint)
    if not isinstance(readback,dict) or readback.get("path")!=path:
        raise ValueError("daily index readback missing")
    if base64.b64decode(readback.get("content",""))!=raw:
        raise ValueError("daily index readback mismatch")
    return {"status":"INDEX_VERIFIED","path":path,
            "entries_count":index["entries_count"],"trade_gate":"BLOCKED"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--out",required=True)
    a=p.parse_args()
    local=json.loads(Path(a.snapshot).read_text())
    stamp=dt.datetime.fromisoformat(local["asof"])
    if stamp.utcoffset()!=dt.timedelta(hours=8):
        raise ValueError("missing Shanghai timestamp")
    index=build(a.repo,stamp.date().isoformat())
    # The just-archived snapshot MUST be in the remote date index.
    run=int(os.environ["GITHUB_RUN_ID"])
    attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT","1"))
    if not any(x["run_id"]==run and x["run_attempt"]==attempt for x in index["entries"]):
        raise ValueError("current immutable snapshot not present in index")
    result=persist(a.repo,index)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":main()
