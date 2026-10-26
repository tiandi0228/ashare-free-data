"""Bounded official-source research scouting against *all* P1-audited issuers.

This is a discovery bridge, not an official PIT state certification or
a source of tradable orders. Rotate three issuers per new four-shard P1 run.
"""
import argparse,json,re
from collections import defaultdict
from datetime import date
from pathlib import Path

CODE=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
KINDS={"listing","st","halt","delisting"}

def plan(full_queue,limit=3):
    q=full_queue
    if (q.get("phase")!="P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST"
        or q.get("trade_gate")!="BLOCKED"
        or q.get("historical_PIT_verified") is not False
        or q.get("independently_verified_official_PIT_cells")!=0
        or q.get("full_historical_status_coverage_authenticated") is not False
        or q.get("latest_quote_freshness_authenticated") is not False):
        raise ValueError("unsafe full P1 official-source worklist")
    count=q.get("completed_issuers_replayed");shards=q.get("completed_shards_replayed")
    tasks=q.get("official_evidence_tasks")
    if (type(count)!=int or not 1<=count<=10000 or
        type(shards)!=int or not 1<=shards<=10000 or
        type(limit)!=int or limit!=3 or not isinstance(tasks,list)
        or len(tasks)!=q.get("required_official_evidence_cells")):
        raise ValueError("invalid full-archive queue accounting")
    by_issuer=defaultdict(lambda:{"days":set(),"kinds":set(),"shards":set(),"sources":set()})
    seen=set()
    for item in tasks:
        code=item.get("issuer");day=item.get("decision_day");kind=item.get("status_kind")
        digest=item.get("vendor_csv_sha256")
        key=(code,day,kind)
        if (not isinstance(code,str) or not CODE.fullmatch(code)
            or not isinstance(day,str) or not isinstance(kind,str) or kind not in KINDS
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or item.get("status")!="OFFICIAL_PIT_EVIDENCE_REQUIRED"
            or item.get("historical_asof_verified") is not False
            or item.get("official_publisher_authenticated") is not False
            or item.get("whole_day_state_coverage_authenticated") is not False
            or item.get("official_original_sha256") is not None
            or item.get("official_first_publication_utc") is not None
            or key in seen):
            raise ValueError("unsupported or duplicated historical PIT evidence claim")
        seen.add(key)
        try:
            decision=date.fromisoformat(day)
            cutoff=date.fromisoformat(q["frozen_vendor_query_end"])
        except (KeyError,ValueError,TypeError) as exc:raise ValueError("invalid historical date") from exc
        if decision>cutoff:raise ValueError("decision date after frozen source")
        d=by_issuer[code];d["days"].add(day);d["kinds"].add(kind)
        d["shards"].add(item.get("source_shard"));d["sources"].add(digest)
    if len(by_issuer)!=count:raise ValueError("missing P1 source issuer")
    for issuer,d in by_issuer.items():
        if len(d["shards"])!=1 or len(d["sources"])!=1 or d["kinds"]!=KINDS:
            raise ValueError("inconsistent original P1 issuer evidence cells")
        if len([x for x in tasks if x["issuer"]==issuer])!=len(d["days"])*4:
            raise ValueError("issuer evidence count mismatch")
    issuers=sorted(by_issuer,key=lambda c:(next(iter(by_issuer[c]["shards"])),c))
    start=(max(0,shards//4-1)*3)%count
    picks=[issuers[(start+i)%count] for i in range(min(limit,count))]
    targets=[{"issuer":issuer,"observed_decision_dates":sorted(by_issuer[issuer]["days"]),
              "cells_to_research":len(by_issuer[issuer]["days"])*4,
              "original_official_url":None,"original_publication_time":None,
              "research_state":"SOURCE_DISCOVERY_REQUIRED_NOT_CERTIFIED"} for issuer in picks]
    return {"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
            "source_roster_sha256":q["roster_source_sha256"],
            "full_source_issuers":count,"full_source_pending_cells":len(tasks),
            "rotating_start_index":start,
            "unmatched_issuer_kind_targets":len(targets)*4,
            "unmatched_cells":sum(t["cells_to_research"] for t in targets),
            "targets":targets,"official_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    q=plan(json.loads(Path(a.queue).read_text()))
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in q.items() if k!="targets"}))
if __name__=="__main__":main()
