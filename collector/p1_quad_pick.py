"""Select up to four distinct, missing shards of the same immutable P1 roster."""
import argparse,json,os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def choose(plan,prior=None,start_index=0,limit=4):
    if plan.get("phase")!="P1_FRESH_VENDOR_SHARD_PLAN" or plan.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid frozen roster")
    count=plan["shard_count"]
    if type(count)!=int or count<1 or len(plan["shards"])!=count:raise ValueError("invalid count")
    done=set()
    if prior is not None:
        if prior.get("source_sha256")!=plan["source_sha256"] or prior.get("shard_count")!=count or prior.get("trade_gate")!="BLOCKED":
            raise ValueError("checkpoint epoch mismatch")
        indices=[x["index"] for x in prior["completed"]]
        if len(indices)!=len(set(indices)) or any(type(i)!=int or i<0 or i>=count for i in indices):
            raise ValueError("invalid checkpoint indices")
        done=set(indices)
    if type(start_index)!=int or start_index<0 or start_index>=count or limit!=4:
        raise ValueError("invalid shard selection")
    order=list(range(start_index,count))+list(range(start_index))
    return [i for i in order if i not in done][:limit]

def rotating_start(shard_count,run_number=None):
    if type(shard_count) is not int or shard_count<1:
        raise ValueError('invalid shard count')
    if run_number is None:
        now=datetime.now(ZoneInfo('Asia/Shanghai'))
        run_number=now.date().toordinal()*12+now.hour//2
    if type(run_number) is not int or run_number<0:
        raise ValueError('invalid run number')
    # A stride coprime to the shard count visits every possible starting index.
    # Multiples of four only visit 100 distinct starts for a 400-shard plan,
    # repeatedly binding the same four issuers to a failing shard.
    return (run_number*(shard_count-1))%shard_count

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True);p.add_argument("--prior")
    p.add_argument("--output-file",required=True)
    a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prior=json.loads(Path(a.prior).read_text()) if a.prior else None
    run_number=os.environ.get("GITHUB_RUN_NUMBER")
    start=rotating_start(plan["shard_count"],int(run_number) if run_number is not None else None)
    # Reliability pilot: one independently verifiable shard per workflow run.
    # A later failed shard must not prevent a successful first shard from
    # reaching the archive audit and durable checkpoint steps.
    selected=choose(plan,prior,start_index=start)[:1]
    if not selected:raise ValueError("all P1 shards completed: do not recapture")
    with Path(a.output_file).open("a") as out:
        for n,key in enumerate(("first","second","third","fourth")):
            present=n<len(selected)
            print(f"has_{key}={str(present).lower()}",file=out)
            print(f"{key}={selected[n]:04d}" if present else f"{key}=NONE",file=out)
    print(json.dumps({"phase":"P1_FOUR_SHARD_PICK","selected":selected,
                      "source_sha256":plan["source_sha256"],"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
