"""Select up to four distinct, missing shards of the same immutable P1 roster."""
import argparse,json
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

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True);p.add_argument("--prior")
    p.add_argument("--output-file",required=True)
    a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    prior=json.loads(Path(a.prior).read_text()) if a.prior else None
    start=0 if prior is not None else datetime.now(ZoneInfo("Asia/Shanghai")).date().toordinal()%plan["shard_count"]
    selected=choose(plan,prior,start_index=start)
    if not selected:raise ValueError("all P1 shards completed: do not recapture")
    with Path(a.output_file).open("a") as out:
        for n,key in enumerate(("first","second","third","fourth")):
            present=n<len(selected)
            print(f"has_{key}={str(present).lower()}",file=out)
            print(f"{key}={selected[n]:04d}" if present else f"{key}=NONE",file=out)
    print(json.dumps({"phase":"P1_FOUR_SHARD_PICK","selected":selected,
                      "source_sha256":plan["source_sha256"],"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
