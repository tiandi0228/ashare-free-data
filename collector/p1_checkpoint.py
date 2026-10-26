"""Fail-closed durable GitHub Contents checkpoint of research-only shard ledger.

The GitHub Actions workflow may save compact progress metadata to main.
Never store trading orders, secrets, or mark official/PIT certification.
"""
import argparse, base64, json, os, subprocess
from pathlib import Path

CHECKPOINT="evidence/p1_checkpoint.json"

def epoch_path(sha):
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("invalid source SHA256 for checkpoint epoch")
    return "evidence/checkpoints/"+sha+".json"

def validate(ledger):
    if ledger.get("phase")!="P1_ROSTER_SHARD_LEDGER" or ledger.get("trade_gate")!="BLOCKED" or ledger.get("historical_PIT_verified") is not False:
        raise ValueError("unsafe checkpoint")
    if ledger.get("orders")!=[] or ledger.get("executable_candidates")!=[]:
        raise ValueError("unsafe trade fields")
    if type(ledger.get("shard_count")) is not int or not 1<=ledger["shard_count"]<=10000:
        raise ValueError("invalid checkpoint shard count")
    epoch_path(ledger.get("source_sha256"))
    done=ledger.get("completed")
    if not isinstance(done,list) or any(not isinstance(x,dict) for x in done):
        raise ValueError("invalid completed shard records")
    if (type(ledger.get("completed_shards")) is not int or
        type(ledger.get("completed_issuers")) is not int or
        len(done)!=ledger["completed_shards"] or
        any(type(x.get("issuer_count")) is not int for x in done) or
        sum(x["issuer_count"] for x in done)!=ledger["completed_issuers"]):
        raise ValueError("inconsistent checkpoint counts")
    if any(type(x.get("index")) is not int or type(x.get("issuer_count")) is not int or not 0<=x["index"]<ledger["shard_count"] or not 1<=x["issuer_count"]<=8 or len(x.get("receipt_sha256",""))!=64 for x in done):
        raise ValueError("invalid checkpoint entries")
    if len({x["index"] for x in done})!=len(done):
        raise ValueError("duplicated checkpoint shards")
    for item in done:
        for key in ("manifest_sha256","receipt_sha256"):
            digest=item.get(key)
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("invalid checkpoint evidence digest")
    expected_pending=[i for i in range(ledger["shard_count"]) if i not in {x["index"] for x in done}]
    if ledger.get("pending_shards")!=expected_pending or ledger.get("next_shard")!=(expected_pending[0] if expected_pending else None):
        raise ValueError("checkpoint pending shard mismatch")
    failed=ledger.get("failed_in_this_reconciliation")
    if ledger.get("full_market_bars_certified") is not False:
        raise ValueError("unsafe checkpoint certification fields")
    if (not isinstance(failed,list) or
        any(type(i) is not int or i<0 or i>=ledger["shard_count"] for i in failed) or
        len(failed)!=len(set(failed))):
        raise ValueError("invalid checkpoint failed shards")
    return ledger

def gh(*args,input_data=None):
    return subprocess.run(["gh","api",*args],input=input_data,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout

def remote_read(repo,path=CHECKPOINT):
    try:
        result=json.loads(gh(f"repos/{repo}/contents/{path}", "-f", "ref=main", "--method", "GET"))
        raw=base64.b64decode(result["content"]).decode()
        return json.loads(raw.removesuffix(chr(92)+"n")),result["sha"]
    except subprocess.CalledProcessError as exc:
        # Only an explicit GitHub 404 means the checkpoint is absent.
        # Authentication, rate-limit and network failures must stop the job.
        if exc.returncode==1 and "404" in (exc.stderr or "") and "Not Found" in (exc.stderr or ""):
            return None,None
        raise

def merge(candidate,previous):
    validate(candidate)
    if previous is None:return candidate
    validate(previous)
    if (candidate["source_sha256"],candidate["shard_count"])!=(previous["source_sha256"],previous["shard_count"]):
        raise ValueError("refusing to overwrite different frozen roster epoch")
    old={x["index"]:x for x in previous["completed"]}
    new={x["index"]:x for x in candidate["completed"]}
    # Conflicting evidence is never acceptable, even when a stale candidate
    # contains fewer shards than the durable remote checkpoint.
    if any(new[index]!=item for index,item in old.items() if index in new):
        raise ValueError("checkpoint would replace historical verified shard evidence")
    if len(new)<len(old):
        if any(index not in old for index in new):
            raise ValueError("stale checkpoint contains unknown shards")
        return previous
    if any(index not in new for index in old):
        raise ValueError("checkpoint would drop historical verified shard evidence")
    return candidate

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["read","write"],required=True)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--in-file")
    p.add_argument("--source-sha")
    p.add_argument("--out",default="evidence/prior_ledger.json")
    a=p.parse_args()
    if not a.repo:raise ValueError("repo required")
    checkpoint=epoch_path(a.source_sha) if a.source_sha else CHECKPOINT
    remote,sha=remote_read(a.repo,checkpoint)
    if a.mode=="read" and remote is None and a.source_sha:
        legacy,_=remote_read(a.repo,CHECKPOINT)
        if legacy is not None and legacy.get("source_sha256")==a.source_sha:
            remote=legacy
    if a.mode=="read":
        if remote is not None:
            validate(remote)
            dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(remote)+chr(10))
            print("Recovered durable GitHub checkpoint with",remote["completed_issuers"],"issuers")
        else:print("No durable checkpoint yet")
        return
    if not a.in_file:raise ValueError("input file required")
    candidate=json.loads(Path(a.in_file).read_text())
    if a.source_sha and candidate.get("source_sha256")!=a.source_sha:
        raise ValueError("checkpoint source SHA mismatch")
    chosen=merge(candidate,remote)
    if chosen is remote:
        print("Preserved higher-progress remote checkpoint")
        return
    data=base64.b64encode((json.dumps(chosen,indent=2,ensure_ascii=False)+chr(10)).encode()).decode()
    params=["-X","PUT",f"repos/{a.repo}/contents/{checkpoint}","-f","message=chore(p1): persist audited no-trade shard checkpoint","-f",f"content={data}","-f","branch=main"]
    if sha:params.extend(["-f",f"sha={sha}"])
    gh(*params)
    print("Saved durable checkpoint, completed issuers",chosen["completed_issuers"])
if __name__=="__main__":main()
