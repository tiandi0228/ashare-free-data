"""P1 workflow remote write-boundary inventory + staged fail-closed preview.

Parses the *actual* immutable run script by exact step names. Every remote
mutation must have a separate source-side write fence; generic job-level
concurrency and a late Worker queue lookup are not sufficient.
Produces NON-EXECUTABLE preview only, never a runnable workflow file.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

PHASE="P1_NATIVE_SOURCE_REMOTE_WRITE_BOUNDARY_STAGING"
# Deliberately enumerate every known remote-repository mutation entrypoint.
# Keep an exact command signature for each, including conditional steps.
REQUIRED={
  "Pin authenticated-by-SHA vendor bytes for repeatable P1 research":("--mode pin","collector.p1_roster_lock","roster_pin"),
  "Recover previously archived but uncheckpointed research shards":("--mode write","collector.p1_checkpoint","orphan_recovery_checkpoint"),
  "Archive raw CSV to durable free Git research branch":("collector.p1_csv_archive","--first","raw_csv_archive"),
  "Persist durable no-trade checkpoint in repository":("--mode write","collector.p1_checkpoint","normal_checkpoint"),
  "Archive recovered historical CSV with its original receipt":("collector.p1_csv_archive","archive(plan","gap_repair_csv_archive"),
  "Persist literal scheduled cron and actual GitHub run creation separately":("collector.p1_schedule_run_provenance","--progress","schedule_source_receipt"),
  "Persist two-shard pilot evidence after durable archive acceptance":("collector.p1_dual_pilot_receipt","--selection","pilot_receipt"),
}
EXTRA_REMOTE_SIGNATURES=(
 "collector.p1_csv_archive","collector.p1_checkpoint --mode write",
 "collector.p1_roster_lock --mode pin",
 "collector.p1_schedule_run_provenance",
 "collector.p1_dual_pilot_receipt",
)
HEADER=re.compile(r"^      - name: (.+)$",re.MULTILINE)
GATE_MARK="python -m collector.p1_shared_scheduler_ownership_prewrite"
def steps(source):
    if not isinstance(source,str) or "name: P1 fresh Baostock mainboard roster observation" not in source:
        raise ValueError("not the expected native source workflow")
    headers=list(HEADER.finditer(source))
    if len(headers)<40:
        raise ValueError("workflow unexpectedly truncated")
    groups=[]
    for i,h in enumerate(headers):
        end=headers[i+1].start() if i+1<len(headers) else len(source)
        groups.append((h.group(1),source[h.start():end]))
    if len(set(name for name,_ in groups))!=len(groups):
        raise ValueError("duplicate workflow step labels: audit ambiguous")
    return groups

def audit(source,require_gate=False):
    groups=steps(source)
    found={}
    for name,body in groups:
        matches=[]
        for signature in EXTRA_REMOTE_SIGNATURES:
            if signature in body:
                matches.append(signature)
        # A signature in a quoted diagnostic is not itself proof of a call:
        # all remotely mutating categories must still resolve exact steps.
        if name in REQUIRED:
            x,y,category=REQUIRED[name]
            if x not in body or y not in body:
                raise ValueError("known remote writer changed without renewed audit: "+name)
            # Pin is one special step; claim checkpoint is a conditional
            # writer inside an otherwise local orphan-recovery step.
            found[name]={"category":category,"step_name":name,
                         "remote_mutation":True,
                         "conditional_or_multi_operation":name in (
                           "Recover previously archived but uncheckpointed research shards",
                           "Archive recovered historical CSV with its original receipt",
                           "Persist literal scheduled cron and actual GitHub run creation separately",
                           "Persist two-shard pilot evidence after durable archive acceptance"),
                         "guard_verified_in_deployed_main":False,
                         "staged_guard_inserted_in_preview":False}
        elif matches:
            # Ignore diagnostic lines that only enumerate module names in an
            # offline unit test, or in notes; flag possible new write sites.
            if "run: " in body and ("python -m collector." in body or "from collector." in body):
                real=[sig for sig in matches
                      if "python -m "+sig in body or "from "+sig in body]
                if real and name not in ("Offline source tests","Publish P1 run diagnostics (research only)"):
                    raise ValueError("unreviewed new remote mutation candidate: "+name)
    if set(found)!=set(REQUIRED):
        raise ValueError("incomplete or renamed remote writer inventory: "+str(set(REQUIRED)-set(found)))
    if "concurrency:\n  group: p1-fresh-mainboard-roster-serial\n  cancel-in-progress: false" not in source:
        raise ValueError("native main serial schedule guard absent")
    if require_gate:
        # A separate, SHA-checked preflight step must precede each writer;
        # a single early check is insufficient for later generation changes.
        names=[n for n,_ in groups]
        for name in REQUIRED:
            idx=names.index(name)
            if idx==0 or names[idx-1]!="OWNERSHIP FENCE BEFORE "+name:
                raise ValueError("missing per-boundary ownership step "+name)
            if GATE_MARK not in groups[idx-1][1]:
                raise ValueError("ownership step missing fail-closed evaluator "+name)
    return {
      "phase":PHASE,
      "source_workflow_sha256":hashlib.sha256(source.encode()).hexdigest(),
      "known_remote_writer_count":len(found),
      "source_remote_writers":list(found.values()),
      "source_serial_concurrency_confirmed":True,
      "all_sources_present":True,
      "per_boundary_gate_required":True,
      "production_gate_deployed":False,
      "production_cutover_authorized":False,
      "external_dispatch_authorized":False,
      "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def render_preview(source):
    base=audit(source)
    # Preview is a textual code-review artifact, deliberately not executable
    # workflow YAML: the source contains a metadata preamble and every
    # synthetic step contains an unconditional exit failure.
    updated=source
    for name in REQUIRED:
        token="      - name: "+name
        check=f"""      - name: OWNERSHIP FENCE BEFORE {name}
        # STAGED PREVIEW ONLY - not production YAML
        run: |
          python -m collector.p1_shared_scheduler_ownership_prewrite --help
          echo "BLOCKED: immutable live owner contract is not yet deployed" >&2
          exit 77
"""
        if updated.count(token)!=1:
            raise ValueError("write step marker ambiguous: "+name)
        updated=updated.replace(token,check+token,1)
    check=audit(updated,require_gate=True)
    return {
      "phase":"P1_NONEXECUTABLE_WRITE_BOUNDARY_CHANGE_REVIEW",
      "source_sha256":base["source_workflow_sha256"],
      "staged_preview_sha256":hashlib.sha256(updated.encode()).hexdigest(),
      "reviewed_boundaries":len(REQUIRED),
      "source_gate_installed":False,
      "staged_gate_is_deliberately_unconditional_block":True,
      "preview_text":"DO NOT DEPLOY OR MERGE AS WORKFLOW\n"+updated,
      "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--preview",type=Path)
    a=p.parse_args()
    source=a.source.read_text()
    result=audit(source)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    if a.preview:
        preview=render_preview(source)
        a.preview.parent.mkdir(parents=True,exist_ok=True)
        a.preview.write_text(json.dumps(preview,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"boundaries":result["known_remote_writer_count"],
        "production_deployed":False,"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
