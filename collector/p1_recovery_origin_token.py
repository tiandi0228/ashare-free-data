"""Strict, non-secret correlation token for bounded P1 research recovery.

A matching token in a target workflow receipt proves only input propagation.
It does not authenticate the dispatch caller, prove archive success, or permit trades.
"""
import argparse,datetime as dt,json,os,re
from pathlib import Path

TOKEN_RE=re.compile(r"p1r-(20\d{6})-([0-2]\d[0-5]\d)-([1-9]\d{0,19})\Z")
def token_for_attempt(attempt):
    if not isinstance(attempt,dict) or attempt.get("phase")!="P1_SINGLE_SHARD_DISPATCH_ATTEMPT":
        raise ValueError("invalid recovery attempt")
    if attempt.get("state")!="DISPATCH_ATTEMPT_RESERVED" or attempt.get("requested_shards")!=1:
        raise ValueError("invalid attempt state")
    run=attempt.get("origin_check_run_id")
    if type(run) is not int or run<1:raise ValueError("invalid origin runner")
    stamp=dt.datetime.fromisoformat(attempt["slot"])
    if stamp.tzinfo is None or stamp.utcoffset()!=dt.timedelta(hours=8) or stamp.minute!=10 or stamp.second or stamp.microsecond:
        raise ValueError("invalid Beijing scheduled slot")
    if stamp.hour not in ((1,8,9,11,13,15,17,19,21,23) if stamp.weekday()<5 else (9,15,19,23)):
        raise ValueError("unapproved slot")
    path=f"recovery-dispatch-attempts/{stamp:%Y-%m-%d}/{stamp:%H%M}.json"
    if attempt.get("attempt_path")!=path:raise ValueError("attempt path mismatch")
    if attempt.get("trade_gate")!="BLOCKED" or attempt.get("orders")!=[] or attempt.get("executable_candidates")!=[]:
        raise ValueError("unsafe attempt")
    token=f"p1r-{stamp:%Y%m%d}-{stamp:%H%M}-{run}"
    if not TOKEN_RE.fullmatch(token):raise ValueError("malformed token")
    return token

def target_receipt(*,token,event_name,run_id,shards,ref):
    base={"phase":"P1_RECOVERY_ORIGIN_INPUT_RECEIPT",
          "workflow_run_id":run_id,"trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],
          "historical_collection_verified":False,
          "causal_dispatch_link_verified":False,
          "token_is_not_authentication":True}
    if not token:
        return dict(base,state="NORMAL_OR_UNTAGGED_COLLECTION",recovery_token=None)
    if event_name!="workflow_dispatch" or shards!="1" or ref!="refs/heads/main":
        raise ValueError("recovery token only valid for one-shard manual dispatch on main")
    m=TOKEN_RE.fullmatch(token)
    if not m:raise ValueError("invalid recovery token")
    day=dt.datetime.strptime(m.group(1),"%Y%m%d").date()
    hhmm=m.group(2)
    stamp=dt.datetime.combine(day,dt.time(int(hhmm[:2]),int(hhmm[2:])))
    if stamp.minute!=10 or stamp.hour not in ((1,8,9,11,13,15,17,19,21,23) if stamp.weekday()<5 else (9,15,19,23)):
        raise ValueError("invalid recovery token slot")
    if type(run_id) is not int or run_id<1:raise ValueError("invalid target run id")
    return dict(base,state="RECOVERY_TOKEN_OBSERVED_UNVERIFIED",
                recovery_token=token,origin_check_run_id=int(m.group(3)),
                slot=f"{day.isoformat()}T{hhmm[:2]}:{hhmm[2:]}:00+08:00")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    receipt=target_receipt(
        token=os.environ.get("P1_RECOVERY_TOKEN",""),
        event_name=os.environ["GITHUB_EVENT_NAME"],
        run_id=int(os.environ["GITHUB_RUN_ID"]),
        shards=os.environ["P1_REQUESTED_SHARDS"],
        ref=os.environ["GITHUB_REF"])
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"state":receipt["state"],"run_id":receipt["workflow_run_id"],
                      "trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
