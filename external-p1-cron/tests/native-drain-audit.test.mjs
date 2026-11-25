import test from "node:test";
import assert from "node:assert/strict";
import {assessDrain} from "../src/native-drain-audit.mjs";

const enabled="name: P1\non:\n  schedule:\n    - cron: '10 1 * * 1-5'\n  workflow_dispatch:\n";
const disabled="name: P1\non:\n  workflow_dispatch:\n";
const now="2026-11-12T06:00:00.000Z";
const old="2026-11-11T08:00:00.000Z";
const early="2026-11-10T20:00:00.000Z";
const run=(id,created_at="2026-11-09T12:00:00Z",status="completed",event="schedule")=>({
 id,created_at,status,event,
 conclusion:status==="completed"?"success":null,
 path:".github/workflows/p1-fresh-vendor-roster.yml",head_branch:"main"
});
const base=()=>({source:disabled,sourceSha:"a".repeat(40),
 runs:{total_count:2,workflow_runs:[run(1),run(2,"2026-11-10T12:00:00Z")]},
 observationUtc:now,disabledSinceUtc:early});
test("live native schedule always vetoes cutover, even with empty run queue",()=>{
 const r=assessDrain({...base(),source:enabled,runs:{total_count:0,workflow_runs:[]}});
 assert.equal(r.reason,"NATIVE_CRON_STILL_ENABLED");
 assert.equal(r.external_dispatch_authorized,false);
 assert.equal(r.trade_gate,"BLOCKED");
});
test("unknown YAML format and forged blob SHA fail closed",()=>{
 assert.equal(assessDrain({...base(),source:"on: [schedule, workflow_dispatch]"}).reason,
   "NATIVE_SCHEDULE_SOURCE_UNVERIFIED");
 assert.equal(assessDrain({...base(),sourceSha:"notsha"}).reason,
   "UNVERIFIED_WORKFLOW_SOURCE_SHA");
});
test("absence of authenticated disable timestamp is insufficient",()=>{
 const r=assessDrain({...base(),disabledSinceUtc:null});
 assert.equal(r.reason,"NO_AUTHENTICATED_NATIVE_CRON_DISABLE_TIME");
 assert.equal(r.old_source_run_drain_certified,false);
});
test("short source drain window always blocked",()=>{
 assert.equal(assessDrain({...base(),disabledSinceUtc:old}).reason,
   "INSUFFICIENT_DRAIN_GRACE_24H");
});
test("incomplete run pagination cannot certify empty queue",()=>{
 const x=base();x.runs.total_count=50;
 assert.equal(assessDrain(x).reason,"INCOMPLETE_OR_INVALID_GITHUB_RUN_ROSTER");
});
test("running and queued historical runs prevent cutover",()=>{
 for(const status of ["in_progress","queued","waiting","requested","pending"]){
   const x=base();x.runs.workflow_runs[0]=run(1,"2026-11-09T12:00:00Z",status);
   assert.equal(assessDrain(x).reason,"P1_RUNS_STILL_ACTIVE_OR_QUEUED");
 }
});
test("native task created after disable date indicates late source race",()=>{
 const x=base();x.runs.workflow_runs[1]=run(2,"2026-11-11T12:00:00Z");
 assert.equal(assessDrain(x).reason,"LATE_NATIVE_SCHEDULE_CREATED_AFTER_CUTOVER");
});
test("unknown late source horizon still cannot receive approval",()=>{
 const r=assessDrain(base());
 assert.equal(r.reason,"NO_HARD_UPPER_BOUND_FOR_GITHUB_SCHEDULE_CREATION");
 assert.equal(r.currentObservationsConsistentWithDrain,true);
 assert.equal(r.external_dispatch_authorized,false);
 assert.equal(r.old_source_run_drain_certified,false);
 assert.deepEqual(r.orders,[]);
});
test("run roster rejects duplicate and wrong branch identities",()=>{
 const x=base();x.runs.workflow_runs[1].id=1;
 assert.equal(assessDrain(x).reason,"UNTRUSTED_SOURCE_RUN_IDENTITY");
 const y=base();y.runs.workflow_runs[0].head_branch="feature";
 assert.equal(assessDrain(y).reason,"UNTRUSTED_SOURCE_RUN_IDENTITY");
});
test("future runner creation and unknown terminal conclusions rejected",()=>{
 const x=base();x.runs.workflow_runs[0].created_at="2026-11-15T00:00:00Z";
 assert.equal(assessDrain(x).reason,"INVALID_RUN_CREATED_AT");
 const y=base();y.runs.workflow_runs[0].conclusion=null;
 assert.equal(assessDrain(y).reason,"UNKNOWN_TERMINAL_RUN_CONCLUSION");
});
