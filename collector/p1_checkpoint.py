"""Fail-closed durable GitHub Contents checkpoint of research-only shard ledger.

The GitHub Actions workflow may save compact progress metadata to main.
Never store trading orders, secrets, or mark official/PIT certification.
"""
import argparse, base64, json, os, subprocess
from pathlib import Path

CHECKPOINT="evidence/p1_checkpoint.json"

def validate(ledger):
    if ledger.get("phase")!="P1_ROSTER_SHARD_LEDGER" or ledger.get("trade_gate")!="BLOCKED" or ledger.get("historical_PIT_verified") is not False:
        raise ValueError("unsafe checkpoint")
    if ledger.get("orders")!=[] or ledger.get("executable_candidates")!=[]:
        raise ValueError("unsafe trade fields")
    done=ledger.get("completed",[])
    if len(done)!=ledger.get("completed_shards") or sum(x["issuer_count"] for x in done)!=ledger.get("completed_issuers"):
        raise ValueError("inconsistent checkpoint counts")
    if len({x["index"] for x in done})!=len(done):
        raise ValueError("duplicated checkpoint shards")
    return ledger

def gh(*args,input_data=None):
    return subprocess.check_output(["gh","api",*args],input=input_data,text=True)

def remote_read(repo):
    try:
        result=json.loads(gh(f"repos/{repo}/contents/{CHECKPOINT}", "-f", "ref=main", "--method", "GET"))
        return json.loads(base64.b64decode(result["content"])),result["sha"]
    except subprocess.CalledProcessError as exc:
        if exc.returncode==1: return None,None
        raise

def merge(candidate,previous):
    validate(candidate)
    if previous is None:return candidate
    validate(previous)
    if (candidate["source_sha256"],candidate["shard_count"])!=(previous["source_sha256"],previous["shard_count"]):
        raise ValueError("refusing to overwrite different frozen roster epoch")
    if candidate["completed_issuers"]<previous["completed_issuers"]:
        return previous
    return candidate

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["read","write"],required=True)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--in-file")
    p.add_argument("--out",default="evidence/prior_ledger.json")
    a=p.parse_args()
    if not a.repo:raise ValueError("repo required")
    remote,sha=remote_read(a.repo)
    if a.mode=="read":
        if remote is not None:
            validate(remote)
            dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(remote)+"\\n")
            print("Recovered durable GitHub checkpoint with",remote["completed_issuers"],"issuers")
        else:print("No durable checkpoint yet")
        return
    if not a.in_file:raise ValueError("input file required")
    candidate=json.loads(Path(a.in_file).read_text())
    chosen=merge(candidate,remote)
    if chosen is remote:
        print("Preserved higher-progress remote checkpoint")
        return
    data=base64.b64encode((json.dumps(chosen,indent=2,ensure_ascii=False)+"\\n").encode()).decode()
    params=["-X","PUT",f"repos/{a.repo}/contents/{CHECKPOINT}","-f","message=chore(p1): persist audited no-trade shard checkpoint","-f",f"content={data}","-f","branch=main"]
    if sha:params.extend(["-f",f"sha={sha}"])
    gh(*params)
    print("Saved durable checkpoint, completed issuers",chosen["completed_issuers"])
if __name__=="__main__":main()
