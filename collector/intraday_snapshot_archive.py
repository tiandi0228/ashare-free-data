"""Immutable, research-only GitHub archival of five-stock intraday snapshots. NO TRADES."""
import argparse,base64,datetime as dt,hashlib,json,os,re,subprocess
from pathlib import Path

BRANCH="research-intraday-snapshots"
PHASE="P1_PUBLIC_INTRADAY_RESEARCH_SNAPSHOT"
WATCHLIST=frozenset(("002249","002696","301015","300015","300896"))
REPO_RE=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

def validate(raw,run_id,attempt):
    if not isinstance(raw,bytes) or not 0<len(raw)<=128*1024:
        raise ValueError("snapshot size invalid")
    snap=json.loads(raw)
    if (not isinstance(snap,dict) or snap.get("phase")!=PHASE
            or snap.get("trade_gate")!="BLOCKED" or snap.get("orders")!=[]
            or snap.get("executable_candidates")!=[]
            or snap.get("provider_type")!="UNOFFICIAL_WEB_ENDPOINTS"):
        raise ValueError("snapshot research-only gate invalid")
    rows=snap.get("symbols")
    if not isinstance(rows,dict) or frozenset(rows)!=WATCHLIST:
        raise ValueError("five-symbol list invalid")
    for row in rows.values():
        if not isinstance(row,dict):
            raise ValueError("malformed symbol")
        gate=row.get("validation",row)
        if (not isinstance(gate,dict)
                or gate.get("trade_gate")!="BLOCKED"
                or gate.get("orders")!=[]
                or gate.get("executable_candidates")!=[]
                or gate.get("executable_quote") is not False
                or row.get("status") not in (None,"SOURCE_UNAVAILABLE")):
            raise ValueError("symbol executable output invalid")
    stamp=dt.datetime.fromisoformat(snap["asof"])
    if stamp.tzinfo is None or stamp.utcoffset()!=dt.timedelta(hours=8):
        raise ValueError("snapshot timestamp not Shanghai local")
    if type(run_id) is not int or run_id<1 or type(attempt) is not int or attempt<1:
        raise ValueError("run identity invalid")
    path=f"snapshots/{stamp.date().isoformat()}/run_{run_id}_attempt_{attempt}.json"
    return path,snap

def api(repo,endpoint,*,method="GET",data=None):
    args=["gh","api",f"repos/{repo}/{endpoint}","--method",method]
    if data is not None:args+=["--input","-"]
    call=subprocess.run(args,input=json.dumps(data) if data is not None else None,
                        capture_output=True,text=True,timeout=45,check=False)
    if call.returncode:
        if "404" in call.stderr and "Not Found" in call.stderr:return None
        raise RuntimeError("GitHub archive API unavailable")
    return json.loads(call.stdout)

def ensure_branch(repo):
    ref=api(repo,f"git/ref/heads/{BRANCH}")
    if ref is not None:
        if not isinstance(ref,dict) or ref.get("ref")!=f"refs/heads/{BRANCH}":
            raise ValueError("wrong archive branch")
        return
    main=api(repo,"git/ref/heads/main")
    if not isinstance(main,dict):raise ValueError("missing main branch")
    sha=main.get("object",{}).get("sha")
    if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise ValueError("invalid main SHA")
    try:
        api(repo,"git/refs",method="POST",data={
            "ref":f"refs/heads/{BRANCH}","sha":sha})
    except RuntimeError:
        ref=api(repo,f"git/ref/heads/{BRANCH}")
        if not isinstance(ref,dict) or ref.get("ref")!=f"refs/heads/{BRANCH}":
            raise

def persist(repo,path,raw):
    if not isinstance(repo,str) or not REPO_RE.fullmatch(repo):
        raise ValueError("invalid repository")
    if not re.fullmatch(r"snapshots/\d{4}-\d\d-\d\d/run_[1-9]\d*_attempt_[1-9]\d*\.json",path):
        raise ValueError("invalid archive path")
    ensure_branch(repo)
    endpoint=f"contents/{path}?ref={BRANCH}"
    existing=api(repo,endpoint)
    if existing is None:
        # Create-only. Never provide an old blob SHA to update another run.
        api(repo,f"contents/{path}",method="PUT",data={
            "message":"archive(p1): immutable five-stock research snapshot [NO TRADES]",
            "branch":BRANCH,"content":base64.b64encode(raw).decode()})
    saved=api(repo,endpoint)
    if not isinstance(saved,dict) or saved.get("path")!=path or not saved.get("sha"):
        raise ValueError("archive readback unavailable")
    if base64.b64decode(saved.get("content",""))!=raw:
        raise ValueError("archive readback differs; overwrite forbidden")
    return dict(status="ARCHIVED_IMMUTABLE_RESEARCH_SNAPSHOT",
                branch=BRANCH,path=path,sha256=hashlib.sha256(raw).hexdigest(),
                blob_sha=saved["sha"],replayable_minute_bars=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--run-id",type=int,default=int(os.environ.get("GITHUB_RUN_ID","0")))
    p.add_argument("--attempt",type=int,default=int(os.environ.get("GITHUB_RUN_ATTEMPT","1")))
    p.add_argument("--out",required=True)
    a=p.parse_args()
    raw=Path(a.snapshot).read_bytes()
    path,_=validate(raw,a.run_id,a.attempt)
    report=persist(a.repo,path,raw)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"path":path,"trade_gate":"BLOCKED"}))

if __name__=="__main__":main()
