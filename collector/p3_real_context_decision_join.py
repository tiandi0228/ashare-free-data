"""Join quarantined PDF context leads to actual bounded P1 decision days; never certify."""
import argparse,json
from pathlib import Path
from collector.p3_real_date_context_triage import classify

def join(worklist,triage):
    if worklist.get("phase")!="P3_P1_OBSERVED_WORKLIST" or triage.get("phase")!="P3_REAL_P1_DATE_CONTEXT_TRIAGE":
        raise ValueError("unexpected input")
    if worklist.get("trade_gate")!="BLOCKED" or triage.get("trade_gate")!="BLOCKED":
        raise ValueError("unsafe gate")
    tasks=worklist["official_evidence_tasks"]
    if len(tasks)!=worklist["official_evidence_cells_required"]:raise ValueError("task mismatch")
    known={x["issuer"] for x in triage["candidate_contexts"]}
    leads=[]
    for t in tasks:
        if t["code"] not in known:continue
        for c in triage["candidate_contexts"]:
            if c["issuer"]!=t["code"]:continue
            if c.get("historical_effective_date_verified") is not False or c.get("historical_publication_time_verified") is not False:
                raise ValueError("unexpected certification")
            leads.append({"issuer":t["code"],"decision_date":t["decision_date"],"status_kind":t["kind"],
                          "announcement_id":c["announcement_id"],"source_sha256":c["original_sha256"],
                          "date_text":c["date_text"],"candidate_event_cues":c["candidate_event_cues"],
                          "decision_date_state_certified":False,
                          "evidence_usable_asof_decision":False})
    return {"phase":"P3_REAL_CONTEXT_P1_DECISION_JOIN",
            "worklist_cells":len(tasks),"research_lead_links":len(leads),
            "research_only_links":leads,"official_pit_certified_cells":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser()
    for n in ("worklist","triage","out"):p.add_argument("--"+n,required=True)
    x=p.parse_args();r=join(json.loads(Path(x.worklist).read_text()),json.loads(Path(x.triage).read_text()))
    dest=Path(x.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="research_only_links"}))
if __name__=="__main__":main()
