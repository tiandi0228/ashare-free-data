"""Immutable research-only P4 current-tail evidence in the free Git archive.

Each successful run/attempt stores exact vendor CSV, source SHA, full event
manifest, independently recomputed result and byte hashes. Never writes P1,
never treats observed crossings as executable trading signals.
"""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from collector.p4_current_tail_ma20_research import verify

BRANCH="research-csv-archive"
CODE=re.compile(r"(?:sh\.[0-9]{6}|sz\.[0-9]{6})\Z")
SHA40=re.compile(r"[0-9a-f]{40}\Z")

def git(*args,cwd=None,env=None,check=True):
    return subprocess.run(["git",*args],cwd=cwd,env=env,
                          check=check,text=True,capture_output=True,timeout=90)

def prepare(epoch,source,run_id,attempt,archive_sha):
    """Validate every observation before producing any archivable bytes."""
    if (not SHA40.fullmatch(str(archive_sha))
        or not str(run_id).isdigit() or int(run_id)<1
        or type(attempt) is not int or not 1<=attempt<=100):
        raise ValueError("invalid evidence provenance")
    folder=Path(source)
    report=json.loads((folder/"current_tail_report.json").read_text())
    if report.get("source_archive_commit")!=archive_sha:
        raise ValueError("capture archive commit changed")
    result=verify(epoch,folder)
    if (result.get("trade_gate")!="BLOCKED" or result.get("orders")!=[]
        or result.get("executable_candidates")!=[]
        or result.get("buy_signals_authorized")!=0
        or result.get("verified_issuers")!=report.get("selected_issuers")):
        raise ValueError("research evidence failed independent audit")
    codes=report.get("selected_codes")
    if (not isinstance(codes,list) or not 1<=len(codes)<=8
        or any(not isinstance(c,str) or not CODE.fullmatch(c) for c in codes)
        or len(set(codes))!=len(codes)):
        raise ValueError("unsafe or non-bounded issuer names")
    files={"current_tail_report.json":(folder/"current_tail_report.json").read_bytes()}
    for code in codes:
        name=code.replace(".","_")+"_current.csv"
        files[name]=(folder/name).read_bytes()
    files["independent_verification.json"]=(json.dumps(result,sort_keys=True,indent=2)+"\n").encode()
    digest={name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())}
    record={"phase":"P4_CURRENT_TAIL_PERMANENT_RESEARCH_RECEIPT",
            "source_archive_commit":archive_sha,
            "source_epoch_sha256":report["source_epoch_sha256"],
            "source_p1_frozen_end":report["frozen_p1_end"],
            "observation_as_of_day":report["as_of_day"],
            "github_run_id":int(run_id),"github_run_attempt":attempt,
            "observed_issuers":result["verified_issuers"],
            "verified_new_vendor_rows":result["new_rows_verified"],
            "non_executable_ma20_crossings":result["verified_non_executable_crossings"],
            "immutable_original_sha256":digest,
            "full_market_coverage":False,"historical_PIT_verified":False,
            "trading_signal_authorized":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    files["permanent_receipt.json"]=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
    folder_name="p4-current-tail/"+report["source_epoch_sha256"][:16]+f"/run_{int(run_id)}_attempt_{attempt}"
    return folder_name,files,record

def stage(work,folder_name,files):
    """Never overwrite differing bytes or adopt unexpected files at same run ID."""
    target=Path(work)/folder_name
    if target.exists():
        existing={p.name for p in target.iterdir() if p.is_file()}
        if existing-set(files) or any(p.is_dir() for p in target.iterdir()):
            raise ValueError("unexpected pre-existing archive objects")
    target.mkdir(parents=True,exist_ok=True)
    for name,raw in files.items():
        if "/" in name or "\\" in name or name.startswith("."):
            raise ValueError("unsafe source filename")
        dest=target/name
        if dest.exists() and dest.read_bytes()!=raw:
            raise ValueError("immutable current-tail archive conflict")
        dest.write_bytes(raw)
    return target

def readback(archive_root,epoch,run_id,attempt,archive_sha):
    """Recompute and compare every permanent byte against archived originals."""
    if not SHA40.fullmatch(str(archive_sha)):
        raise ValueError("invalid source archive sha")
    epoch_sha=json.loads((Path(epoch)/"archive_status.json").read_text())["source_sha256"]
    root=Path(archive_root)/"p4-current-tail"/epoch_sha[:16]
    target=root/f"run_{int(run_id)}_attempt_{attempt}"
    folder_name,files,record=prepare(epoch,target,run_id,attempt,archive_sha)
    if target!=Path(archive_root)/folder_name:
        raise ValueError("archive research path mismatch")
    if not target.is_dir() or {p.name for p in target.iterdir()}!=set(files):
        raise ValueError("permanent archive files incomplete or unexpected")
    for name,raw in files.items():
        if (target/name).read_bytes()!=raw:
            raise ValueError("permanent archive bytes mismatch")
    return {"status":"PERMANENT_READBACK_VERIFIED","path":folder_name,
            "verified_issuers":record["observed_issuers"],
            "verified_non_executable_crossings":record["non_executable_ma20_crossings"],
            "trade_gate":"BLOCKED","orders":[]}

MAX_ARCHIVE_PUSH_ATTEMPTS=3

def is_non_fast_forward_push(result):
    """Only a proven concurrent branch advancement is eligible for retry."""
    if result.returncode==0:
        return False
    message=((result.stderr or "")+"\\n"+(result.stdout or "")).lower()
    return ("non-fast-forward" in message or "(fetch first)" in message
            or "stale info" in message)

def persist(epoch,source,repository,run_id,attempt,archive_sha):
    if (not isinstance(repository,str) or
        not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository)):
        raise ValueError("untrusted repository target")
    if not os.environ.get("GH_TOKEN"):raise ValueError("archive write token unavailable")
    actual=git("rev-parse","HEAD",cwd=epoch).stdout.strip()
    if actual!=archive_sha:raise ValueError("pinned baseline Git commit mismatch")
    # Perform immutable source verification only once against the pinned epoch.
    folder_name,files,record=prepare(epoch,source,run_id,attempt,archive_sha)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        helper=root/"askpass.sh"
        # Never place GitHub authentication data in remote URL or process args.
        helper.write_text('#!/bin/sh\\ncase "$1" in\\n  *Username*) printf "x-access-token";;\\n  *Password*) printf "%s" "$GH_TOKEN";;\\nesac\\n')
        helper.chmod(0o700)
        env={**os.environ,"GIT_ASKPASS":str(helper),"GIT_TERMINAL_PROMPT":"0"}
        for try_index in range(1,MAX_ARCHIVE_PUSH_ATTEMPTS+1):
            # Starting from a fresh latest remote tree preserves *every* P1
            # shard and any other immutable P4 evidence added concurrently.
            work=root/("archive_"+str(try_index))
            git("clone","--depth=1","--branch",BRANCH,"--single-branch",
                "https://github.com/"+repository+".git",str(work),env=env)
            git("config","user.name","github-actions[bot]",cwd=work)
            git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=work)
            stage(work,folder_name,files)
            git("add",folder_name,cwd=work)
            dirty=git("diff","--cached","--quiet",cwd=work,check=False).returncode!=0
            if dirty:
                git("commit","-m",
                    "data(p4): immutable current-tail MA20 research evidence [NO TRADES]",
                    cwd=work)
                push=git("push","origin",f"HEAD:refs/heads/{BRANCH}",
                         cwd=work,env=env,check=False)
                if push.returncode!=0:
                    if (is_non_fast_forward_push(push)
                        and try_index<MAX_ARCHIVE_PUSH_ATTEMPTS):
                        continue
                    if is_non_fast_forward_push(push):
                        raise ValueError("concurrent immutable archive writes exhausted bounded retry")
                    raise ValueError("immutable research archive push rejected (not a retryable concurrent update)")
            commit=git("rev-parse","HEAD",cwd=work).stdout.strip()
            remote_out=git("ls-remote","origin",f"refs/heads/{BRANCH}",
                           cwd=work,env=env).stdout.strip().split()
            if not remote_out or remote_out[0]!=commit:
                raise ValueError("permanent archive remote readback mismatch")
            return {"persisted":True,"branch":BRANCH,"path":folder_name,
                "archive_commit_sha":commit,"attempted_git_writes":try_index,
                "observed_issuers":record["observed_issuers"],
                "verified_new_vendor_rows":record["verified_new_vendor_rows"],
                "non_executable_ma20_crossings":record["non_executable_ma20_crossings"],
                "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[]}
        raise ValueError("permanent archive not confirmed")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("archive","readback"),required=True)
    p.add_argument("--epoch",required=True);p.add_argument("--source")
    p.add_argument("--archive-root")
    p.add_argument("--repository",default=os.getenv("GITHUB_REPOSITORY"))
    p.add_argument("--source-run",required=True)
    p.add_argument("--run-attempt",required=True,type=int)
    p.add_argument("--archive-sha",required=True)
    a=p.parse_args()
    if a.mode=="archive":
        if not a.source:p.error("--source is required for archive")
        result=persist(a.epoch,a.source,a.repository,a.source_run,a.run_attempt,a.archive_sha)
    else:
        if not a.archive_root:p.error("--archive-root is required for readback")
        result=readback(a.archive_root,a.epoch,a.source_run,a.run_attempt,a.archive_sha)
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
