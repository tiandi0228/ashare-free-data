"""Archive validated CSV shards to a free Git branch, independent from main.

A bounded job archives only the two newly validated shards. Failures do not
mark long-term CSV persistence as successful. No trading or certification.
"""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
from collector.p1_roster_shard_manifest import CODE

BRANCH="research-csv-archive"

def git(*args,cwd=None,check=True):
    return subprocess.run(["git",*args],cwd=cwd,check=check,text=True,capture_output=True,timeout=90)

def collect(plan, selected):
    files=[]
    seen_codes=set()
    seen_shards=set()
    for index,folder in selected:
        if type(index) is not int or not 0<=index<len(plan["shards"]) or index in seen_shards:
            raise ValueError("invalid or duplicate archive shard index")
        seen_shards.add(index)
        shard=plan["shards"][index]
        receipt=json.loads((folder/"quality.json").read_text())
        if receipt["manifest_sha256"]!=shard["sha256"] or receipt["issuer_count"]!=shard["count"]:
            raise ValueError("shard receipt mismatch")
        if receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or receipt.get("trade_gate")!="BLOCKED":
            raise ValueError("unsafe receipt")
        results=receipt.get("results")
        if not isinstance(results,list) or len(results)!=shard["count"]:
            raise ValueError("incomplete archive receipt")
        for item in results:
            if not isinstance(item,dict) or item.get("status")!="OBSERVED_UNVERIFIED":
                raise ValueError("invalid issuer result status in archive batch")
            code=item.get("code") if isinstance(item,dict) else None
            if not isinstance(code,str) or not CODE.fullmatch(code) or code in seen_codes:
                raise ValueError("invalid or duplicate issuer in archive batch")
            seen_codes.add(code)
            source=folder/(code.replace(".","_")+".csv")
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item["sha256"]:
                raise ValueError("CSV digest mismatch")
            files.append((index,source,item["sha256"]))
        codes=[item.get("code") for item in results if isinstance(item,dict)]
        if len(codes)!=len(results) or any(not isinstance(code,str) or not CODE.fullmatch(code) for code in codes):
            raise ValueError("invalid archive batch issuer membership")
        membership=hashlib.sha256(("".join(code+"\n" for code in sorted(codes))).encode()).hexdigest()
        if membership!=shard["sha256"]:
            raise ValueError("archive issuer membership differs from original shard manifest")
    return files

MAX_PUSH_ATTEMPTS=3

class P1ArchivePushError(ValueError):
    """Classified bounded archive transport failure; never contains raw stderr."""
    def __init__(self,message,category,attempts):
        self.category=category
        self.attempts=attempts
        super().__init__(message+" ["+category+"]")


def classify_push_failure(result):
    """Enumerated diagnosis only. NEVER export git stderr/URLs/tokens into logs."""
    output=((getattr(result,"stderr","") or "")+"\n"+
            (getattr(result,"stdout","") or "")).lower()
    if is_concurrent_push_rejection(result):
        return "CONCURRENT_NON_FAST_FORWARD"
    if any(x in output for x in (
        "permission denied", "http 403", "403 forbidden",
        "authentication failed", "bad credentials",
        "write access to repository not granted",
        "could not read username", "http 401", "401 unauthorized",
    )):
        return "PUSH_AUTH_OR_CONTENTS_WRITE_DENIED"
    if any(x in output for x in (
        "protected branch", "repository rule", "ruleset",
        "push declined due to repository rule",
    )):
        return "BRANCH_PROTECTION_OR_RULESET"
    if any(x in output for x in (
        "exceeds github's file size limit", "file size limit",
        "exceeds file size", "large files detected",
        "pack exceeds maximum", "repository size limit",
    )):
        return "REMOTE_SIZE_QUOTA_OR_FILE_LIMIT"
    if any(x in output for x in (
        "internal server error", "http 500", "http 502", "http 503",
        "service unavailable", "remote end hung up",
    )):
        return "REMOTE_SERVICE_OR_TRANSPORT_FAILURE"
    if any(x in output for x in (
        "connection reset", "could not resolve host",
        "connection timed out", "failed to connect",
        "tls handshake", "ssl connection",
    )):
        return "NETWORK_OR_TLS_FAILURE"
    if any(x in output for x in (
        "pre-receive hook declined", "hook declined",
        "failed to push some refs",
    )):
        return "REMOTE_REJECTED_UNCLASSIFIED"
    return "PUSH_REJECTED_REASON_NOT_AVAILABLE"


def failed_push_receipt(exc,plan,a):
    """No-success immutable diagnostic artifact, never change P1 checkpoint."""
    selected=[x for x in (a.first,a.second,a.third,a.fourth) if x is not None]
    return {
        "phase":"P1_ARCHIVE_PUSH_FAILURE_DIAGNOSTIC_NO_TRADES",
        "status":"FAILED_NO_ARCHIVE_DURABILITY_ATTESTATION",
        "reason_category":exc.category,
        "attempts":exc.attempts,
        "source_sha256":plan.get("source_sha256"),
        "attempted_shard_indices":selected,
        "github_run_id":os.getenv("GITHUB_RUN_ID"),
        "github_run_event":os.getenv("GITHUB_EVENT_NAME"),
        "raw_git_stderr_recorded":False,
        "permanent_csv_durability_certified":False,
        "new_completed_shards_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
        "buy_recommendations_authorized":False,
    }

def is_concurrent_push_rejection(result):
    """Retry ONLY when Git explicitly reports another writer advanced branch."""
    if result.returncode==0:
        return False
    reason=((result.stderr or "")+"\n"+(result.stdout or "")).lower()
    return any(marker in reason for marker in (
        "non-fast-forward", "(fetch first)", "stale info",
    ))

def archive(plan, selected, repository):
    # The complete, unmodified local P1 original receipts are validated once.
    # A retry always stages these same bytes onto a freshly fetched archive.
    entries=collect(plan,selected)
    prefix=plan["source_sha256"][:16]
    if not repository or "/" not in repository:raise ValueError("GitHub repository required")
    with tempfile.TemporaryDirectory() as tmp:
        for attempt in range(1,MAX_PUSH_ATTEMPTS+1):
            work=Path(tmp)/f"archive_attempt_{attempt}"
            # Shallow clone avoids downloading the full history each attempt.
            git("clone","--no-checkout","--depth=1",f"https://github.com/{repository}.git",str(work))
            git("config","user.name","github-actions[bot]",cwd=work)
            git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=work)
            found=git("ls-remote","--heads","origin",BRANCH,cwd=work).stdout.strip()
            if found:
                git("fetch","--depth=1","origin",BRANCH,cwd=work)
                git("checkout","-B",BRANCH,"FETCH_HEAD",cwd=work)
            else:
                git("checkout","--orphan",BRANCH,cwd=work)
                for item in work.iterdir():
                    if item.name!=".git":
                        if item.is_dir():shutil.rmtree(item)
                        else:item.unlink()
            for index,folder in selected:
                receipt_source=folder/"quality.json"
                receipt_dest=work/prefix/f"shard_{index:04d}"/"quality.json"
                receipt_dest.parent.mkdir(parents=True,exist_ok=True)
                if receipt_dest.exists() and receipt_dest.read_bytes()!=receipt_source.read_bytes():
                    raise ValueError("refuse to overwrite archived receipt")
                shutil.copyfile(receipt_source,receipt_dest)
            for index,source,digest in entries:
                destination=work/prefix/f"shard_{index:04d}"/source.name
                destination.parent.mkdir(parents=True,exist_ok=True)
                if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()!=digest:
                    raise ValueError("refuse to overwrite archived CSV")
                shutil.copyfile(source,destination)
            manifest=work/prefix/"archive_status.json"
            previous=(json.loads(manifest.read_text()) if manifest.exists() else
                      {"source_sha256":plan["source_sha256"],
                       "trade_gate":"BLOCKED","archived_shards":[]})
            if previous["source_sha256"]!=plan["source_sha256"] or previous["trade_gate"]!="BLOCKED":
                raise ValueError("archive epoch mismatch")
            previous["archived_shards"]=sorted(set(previous["archived_shards"])|
                                               {i for i,_,_ in entries})
            manifest.write_text(json.dumps(previous,indent=2)+chr(10))
            git("add",".",cwd=work)
            if git("diff","--cached","--quiet",cwd=work,check=False).returncode==0:
                print("Archive already up to date on latest remote version")
                return
            git("commit","-m","data(p1): archive SHA-verified research CSV shards [NO TRADES]",cwd=work)
            result=git("push","origin",f"HEAD:refs/heads/{BRANCH}",cwd=work,check=False)
            if result.returncode==0:
                print("Archived",len(entries),"SHA-verified CSV files to",BRANCH,
                      "on write attempt",attempt)
                return
            if is_concurrent_push_rejection(result):
                if attempt<MAX_PUSH_ATTEMPTS:
                    print("P1 archive concurrent update; refreshing latest Git snapshot",
                          "next attempt",attempt+1,flush=True)
                    continue
                raise P1ArchivePushError(
                    "immutable P1 archive concurrent writes exhausted bounded retries",
                    "CONCURRENT_NON_FAST_FORWARD_RETRIES_EXHAUSTED",attempt)
            raise P1ArchivePushError(
                "immutable P1 archive push rejected; not retryable as concurrent update",
                classify_push_failure(result),attempt)
        raise ValueError("P1 archive has no accepted remote write")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True)
    p.add_argument("--first",required=True,type=int)
    p.add_argument("--second",type=int)
    p.add_argument("--third",type=int)
    p.add_argument("--fourth",type=int)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    selected=[(a.first,Path("evidence/first_shard"))]
    if a.second is not None:selected.append((a.second,Path("evidence/second_shard")))
    if a.third is not None:selected.append((a.third,Path("evidence/third_shard")))
    if a.fourth is not None:selected.append((a.fourth,Path("evidence/fourth_shard")))
    if len(set(i for i,_ in selected))!=len(selected) or len(selected)>4:raise ValueError("invalid archive selection")
    try:
        archive(plan,selected,a.repo)
    except P1ArchivePushError as exc:
        # Never report source shards as durable from a failed git push.
        # The existing workflow always uploads evidence/ on failure.
        out=Path("evidence/p1_archive_push_failure.json")
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(failed_push_receipt(exc,plan,a),indent=2)+"\n")
        print("P1 ARCHIVE PUSH FAILED:",exc.category,
              "attempts",exc.attempts,
              "DURABLE SHARDS NOT CERTIFIED; trade_gate BLOCKED",flush=True)
        raise
if __name__=="__main__":main()
