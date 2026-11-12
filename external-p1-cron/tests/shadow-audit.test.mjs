import test from "node:test";
import assert from "node:assert/strict";
import {shadow} from "../src/shadow-audit.mjs";

const origin={
 id:43119727655, name:"P1 origin 10 17 * * 0-4 [NO TRADES]",
 event:"schedule",created_at:"2026-11-11T23:25:37Z",
 status:"completed",conclusion:"success",
 path:".github/workflows/p1-fresh-vendor-roster.yml",head_branch:"main"
};
const older={...origin,id:43000000001,created_at:"2026-11-11T16:00:00Z"};
const row={
 run_id:origin.id,trigger:"schedule",
 inferred_nominal_slot_utc:"2026-11-11T17:10:00+00:00",
 created_at_utc:"2026-11-11T23:25:37+00:00",
 scheduled_creation_lag_minutes:375.617,
 durable_sha_lineage_verified:true,sampled_original_shards_accepted:1
};
function fixture(){
 return [{
  phase:"P1_OBSERVED_SCHEDULE_LATENCY_AND_DURABLE_SHARD_ATTESTATION",
  active_completed_shards:241,active_total_shards:400,trade_gate:"BLOCKED",
  runs:[structuredClone(row)]
 },{total_count:2,workflow_runs:[structuredClone(origin),structuredClone(older)]}];
}
test("late 375.617 minute run exposes possible external duplicate counterfactual",()=>{
 const r=shadow(...fixture());
 assert.equal(r.evaluated_scheduled_runs,1);
 assert.equal(r.severe_delayed_runs,1);
 assert.equal(r.counterfactual_recovery_eligible_runs,1);
 assert.equal(r.possible_late_source_overlap_runs,1);
 assert.equal(r.rows[0].retrospective_worker_decision,"ELIGIBLE_TO_RESERVE_ONE_ATTEMPT");
 assert.equal(r.external_dispatch_enabled,false);
 assert.equal(r.extra_collection_started,false);
 assert.equal(r.trade_gate,"BLOCKED");
});
test("on-time upstream run blocks recovery at +75 minutes",()=>{
 const [report,data]=fixture();
 report.runs[0].created_at_utc="2026-11-11T17:20:00+00:00";
 report.runs[0].scheduled_creation_lag_minutes=10;
 data.workflow_runs[0].created_at="2026-11-11T17:20:00Z";
 const r=shadow(report,data);
 assert.equal(r.counterfactual_recovery_eligible_runs,0);
 assert.equal(r.possible_late_source_overlap_runs,0);
 assert.equal(r.rows[0].retrospective_worker_decision,"P1_RUN_ALREADY_STARTED_AFTER_SLOT");
});
test("no preceding visible Actions run means shadow refuses proof",()=>{
 const [report,data]=fixture();
 data.workflow_runs=[data.workflow_runs[0]];
 data.total_count=1;
 const r=shadow(report,data);
 assert.equal(r.counterfactual_recovery_eligible_runs,0);
 assert.equal(r.rows[0].retrospective_worker_decision,"UNTRUSTED_RUN_COVERAGE");
});
test("reject wrong epoch report, missing source, and contradictory timestamps",()=>{
 const [c,d]=fixture();c.active_completed_shards=242;
 assert.throws(()=>shadow(c,d));
 const [e,f]=fixture();e.runs[0].created_at_utc="2026-11-11T23:25:38+00:00";
 assert.throws(()=>shadow(e,f));
 const [g,h]=fixture();h.workflow_runs=[];
 assert.throws(()=>shadow(g,h));
});
test("unknown cron slot must not be silently accepted",()=>{
 const [a,b]=fixture();
 a.runs[0].inferred_nominal_slot_utc="2026-11-11T17:11:00+00:00";
 a.runs[0].scheduled_creation_lag_minutes=374.617;
 assert.throws(()=>shadow(a,b),/UNMAPPED_WORKER_CRON/);
});
