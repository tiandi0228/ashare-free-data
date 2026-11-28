"""Read-only residual priority queue; retrospective notices are never limit proof."""
import argparse,json,re
from datetime import date
from pathlib import Path

def build(queue,leads):
    for r in (queue,leads):
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["official_limit_certified"]!=0 or r["historical_PIT_verified"] is not False:
            raise ValueError("unsafe input")
    if queue["asof"]!=leads["asof"] or queue["asof"]!="2026-11-25":
        raise ValueError("epoch mismatch")
    tasks={}
    for t in queue["tasks"]:
        if t["priority"]!="P1_DIRECTIONAL":continue
        key=(t["code"],t["day"])
        if key in tasks or not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",key[0]) or not re.fullmatch(r"[a-f0-9]{64}",t["extension_sha256"]):
            raise ValueError("duplicate or malformed task")
        if date.fromisoformat(key[1])>date.fromisoformat(queue["asof"]):raise ValueError("future task")
        tasks[key]=t
    if len(tasks)!=23 or leads["priority_targets"]!=23:raise ValueError("scope mismatch")
    covered=set()
    for r in leads["records"]:
        k=(r["code"],r["day"])
        if k in covered or k not in tasks or not re.fullmatch(r"[a-f0-9]{64}",r["source_sha256"]):
            raise ValueError("invalid lead")
        if any(r.get(f) is not False for f in ("official_limit_verified","first_publication_verified","fill_verified")):
            raise ValueError("unexpected certification")
        covered.add(k)
    if len(covered)!=leads["original_notice_leads"]:raise ValueError("lead count mismatch")
    remaining=[dict(t,notice_lead_found=False,official_limit_verified=False) for k,t in tasks.items() if k not in covered]
    return dict(asof=queue["asof"],source_artifact_sha256=queue["source_artifact_sha256"],priority_targets=len(tasks),existing_notice_leads=len(covered),remaining_notice_tasks=len(remaining),tasks=remaining,official_limit_certified=0,historical_PIT_verified=False,execution_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","leads","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=build(json.loads(a.queue.read_bytes()),json.loads(a.leads.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_RESIDUAL_NOTICE_QUEUE:",json.dumps(r))
