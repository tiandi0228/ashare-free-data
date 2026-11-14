"""Seven-boundary P1 scheduler ownership rehearsal, entirely in memory.

Uses exact live P1 step inventory and SHA-bound staged owner contracts. This
models a late original run encountering freeze/cutover *between* write sites.
No GH token, no remote mutation, no actual writer permission is implemented.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from collector.p1_native_remote_write_boundary_inventory import REQUIRED,audit
from collector.p1_shared_scheduler_ownership_prewrite import EPOCH,WORKFLOW,evaluate

PHASE="P1_SEVEN_REMOTE_WRITERS_OWNER_TRANSITION_IN_MEMORY_REHEARSAL"
NATIVE_START="2026-11-12T00:00:00Z"
SWITCH_START="2026-11-12T01:30:00Z"
RUN_CREATED="2026-11-12T01:10:00Z"
RUN_OBSERVED="2026-11-12T01:45:00Z"

def contract(owner,generation,effective):
    return {
        "phase":"P1_SHARED_SCHEDULER_OWNERSHIP_V1",
        "source_epoch_sha256":EPOCH,"generation":generation,
        "owner":owner,"effective_from_utc":effective,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "allow_write_before_fence_confirmation":False,
    }

def attest(item):
    raw=(json.dumps(item,sort_keys=True)+"\n").encode()
    digest=hashlib.sha256(raw).hexdigest()
    blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
    return raw,digest,blob

def run_for(item,digest,blob,*,event="schedule",created=RUN_CREATED,checked=RUN_OBSERVED):
    return {
        "run_created_at_utc":created,
        "ownership_checked_at_utc":checked,
        "source_epoch_sha256":EPOCH,
        "workflow_path":WORKFLOW,"branch":"main",
        "run_event":event,"run_id":432100001,
        "run_attempt":1,"head_sha":"b"*40,
        "observed_contract_generation":item["generation"],
        "observed_contract_blob_sha":blob,
        "observed_contract_bytes_sha256":digest,
        "native_schedule_currently_enabled":True,
    }

def rehearse(source,*,transition_after=None,mode="FREEZE_ALL",attack=None):
    inventory=audit(source)
    ordered=list(REQUIRED)
    if type(transition_after) not in (int,type(None)) or (
        transition_after is not None and not 0<=transition_after<=len(ordered)
    ):
        raise ValueError("invalid transition boundary")
    if mode not in ("FREEZE_ALL","EXTERNAL_ONLY"):
        raise ValueError("invalid owner transition")
    if attack not in (None,"FORGED_OLD_GENERATION","STALE_RAW_SHA",
                      "MANUAL_RUN","OLD_RUN_CREATED_AFTER_SWITCH"):
        raise ValueError("unknown adversarial case")
    if attack is not None and transition_after is None:
        raise ValueError("adversarial case needs a phase transition")

    results=[]
    for index,name in enumerate(ordered):
        transitioned=transition_after is not None and index>=transition_after
        current=contract(mode,8,SWITCH_START) if transitioned else contract("NATIVE_ONLY",7,NATIVE_START)
        raw,digest,blob=attest(current)
        run=run_for(current,digest,blob)
        if attack=="FORGED_OLD_GENERATION" and transitioned:
            run["observed_contract_generation"]=7
        elif attack=="STALE_RAW_SHA" and transitioned:
            run["observed_contract_bytes_sha256"]="c"*64
        elif attack=="MANUAL_RUN" and transitioned:
            run["run_event"]="workflow_dispatch"
        elif attack=="OLD_RUN_CREATED_AFTER_SWITCH" and transitioned:
            run["run_created_at_utc"]="2026-11-12T01:35:00Z"
        decision=evaluate(current,run,contract_blob_sha=blob,
                          contract_bytes_sha256=digest,contract_raw_bytes=raw)
        if decision.get("trade_gate")!="BLOCKED" or decision.get("orders")!=[] or decision.get("executable_candidates")!=[]:
            raise ValueError("unsafe trade evidence")
        if decision.get("collector_write_authorized") is not False:
            raise ValueError("stage claimed actual source writer authorization")
        if transitioned and decision.get("decision")!="BLOCK":
            raise ValueError("late native source bypassed new owner generation")
        results.append({
            "boundary_index":index,"remote_write_step":name,
            "remote_write_category":REQUIRED[name][2],
            "owner":current["owner"],"generation":current["generation"],
            "owner_contract_git_blob_sha":blob,
            "owner_contract_sha256":digest,
            "research_preflight_decision":decision["decision"],
            "reason":decision["reason"],
            "actual_remote_mutation_attempted":False,
            "collector_write_authorized":False,
        })
    return {
        "phase":PHASE,
        "live_p1_workflow_sha256":inventory["source_workflow_sha256"],
        "source_epoch_sha256":EPOCH,
        "known_remote_writer_count":len(ordered),
        "transition_after_completed_boundary_count":transition_after,
        "adversarial_case":attack,
        "transition_owner":mode,
        "source_side_generation_checks":len(results),
        "pretransition_native_research_eligible":sum(
            r["research_preflight_decision"]=="NATIVE_SCHEDULED_RUN_RESEARCH_ELIGIBLE"
            for r in results),
        "aftertransition_native_blocked":sum(
            r["research_preflight_decision"]=="BLOCK" for r in results),
        "actual_remote_writes":0,
        "actual_git_actions_dispatches":0,
        "production_write_path_integrated":False,
        "all_staged_write_permissions_denied":True,
        "full_P1_to_P4_project_ready":False,
        "rows":results,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def acceptance(source):
    inventory=audit(source)
    transitions=[None,*range(0,len(REQUIRED)+1)]
    scenarios=[]
    for transition in transitions:
        if transition is None:
            cases=[("FREEZE_ALL",None)]
        else:
            cases=[("FREEZE_ALL",None),("EXTERNAL_ONLY",None)]
        for owner,attack in cases:
            scenarios.append(rehearse(source,transition_after=transition,mode=owner,attack=attack))
    # Additional adversarial snapshots at all seven insertion points.
    for index in range(0,len(REQUIRED)):
        for attack in ("FORGED_OLD_GENERATION","STALE_RAW_SHA","MANUAL_RUN","OLD_RUN_CREATED_AFTER_SWITCH"):
            scenarios.append(rehearse(source,transition_after=index,mode="FREEZE_ALL",attack=attack))
    if len(scenarios)!=1+2*(len(REQUIRED)+1)+4*len(REQUIRED):
        raise ValueError("incomplete transition matrix")
    for scenario in scenarios:
        if scenario["actual_remote_writes"]!=0 or scenario["trade_gate"]!="BLOCKED" or scenario["source_side_generation_checks"]!=7:
            raise ValueError("unsafe scenario output")
        transition=scenario["transition_after_completed_boundary_count"]
        expected=0 if transition is None else 7-transition
        if scenario["aftertransition_native_blocked"]!=expected:
            raise ValueError("incomplete post-transition blocking")
    return {
        "phase":"P1_SEVEN_REMOTE_WRITERS_COMPLETE_TRANSITION_MATRIX_READ_ONLY",
        "live_p1_workflow_sha256":inventory["source_workflow_sha256"],
        "tested_source_remote_write_boundaries":7,
        "transition_scenarios":len(scenarios),
        "total_replayed_write_boundary_preflights":sum(x["source_side_generation_checks"] for x in scenarios),
        "all_after_transition_native_attempts_blocked":True,
        "all_actual_remote_writes_zero":True,
        "production_write_path_integrated":False,
        "initial_roster_pin_included":True,
        "conditional_orphan_and_repair_writers_included":True,
        "candidate_cutover_ready":False,
        "details":scenarios,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workflow",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=acceptance(a.workflow.read_text())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
      "scenario_count":result["transition_scenarios"],
      "boundary_checks":result["total_replayed_write_boundary_preflights"],
      "actual_writes":0,"production_integrated":False,
      "trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
