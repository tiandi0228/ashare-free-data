// Retrospective SHADOW analysis only: no HTTP, no dispatch, no marker writes.
// Input is a real read-only P1 Actions API page plus the run-scoped 24h
// post-conclusion SHA-attested schedule-lag audit from the SAME workflow run.
// A counterfactual eligibility is not evidence a Cloudflare trigger ran.
import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {dirname} from "node:path";
import {decide} from "./index.mjs";

const RULES=[
  "25 1,2,4,6,8,10,12,14,16 * * 1-5",
  "25 18 * * 0-4",
  "25 2,8,12,16 * * 6,0"
];
function ruleFor(timeMs){
  const d=new Date(timeMs),wd=d.getUTCDay(),hr=d.getUTCHours();
  if(d.getUTCMinutes()!==25)return null;
  if(hr===18 && wd<=4)return RULES[1];
  if([2,8,12,16].includes(hr) && (wd===6||wd===0))return RULES[2];
  if([1,2,4,6,8,10,12,14,16].includes(hr) && wd>=1&&wd<=5)return RULES[0];
  return null;
}
export function shadow(audit,api){
  if(!audit || audit.phase!=="P1_OBSERVED_SCHEDULE_LATENCY_AND_DURABLE_SHARD_ATTESTATION" ||
     audit.active_completed_shards<241 || audit.active_total_shards!==400 ||
     audit.trade_gate!=="BLOCKED" ||
     !Array.isArray(audit.runs) ||
     !api || !Array.isArray(api.workflow_runs) ||
     api.workflow_runs.length>100 ||
     !Number.isInteger(api.total_count) ||
     api.total_count<api.workflow_runs.length)
    throw Error("SOURCE_AUDIT_OR_GITHUB_COVERAGE_NOT_TRUSTED");
  const seen=new Set();
  const rows=[];
  for(const r of audit.runs){
    if(r.trigger!=="schedule")continue;
    if(!Number.isSafeInteger(r.run_id) || seen.has(r.run_id) ||
       typeof r.inferred_nominal_slot_utc!=="string" ||
       typeof r.created_at_utc!=="string" ||
       !Number.isFinite(r.scheduled_creation_lag_minutes))
       throw Error("UNTRUSTED_SOURCE_RUN");
    seen.add(r.run_id);
    const nominal=Date.parse(r.inferred_nominal_slot_utc);
    const created=Date.parse(r.created_at_utc);
    if(!Number.isFinite(nominal)||!Number.isFinite(created) ||
       Math.abs((created-nominal)/60000-r.scheduled_creation_lag_minutes)>0.002)
      throw Error("SOURCE_TIME_CONTRADICTION");
    const checkMs=nominal+75*60000;
    const rule=ruleFor(checkMs);
    if(rule===null)throw Error("UNMAPPED_WORKER_CRON");
    const sourceRun=api.workflow_runs.filter(x=>x.id===r.run_id);
    if(sourceRun.length!==1 || sourceRun[0].event!=="schedule" ||
       sourceRun[0].created_at!==undefined && Date.parse(sourceRun[0].created_at)!==created)
      throw Error("SOURCE_RUN_NOT_IN_GITHUB_INPUT");
    // A retrospective API page is incomplete evidence of what was listed
    // at +75min. Never invent the source cohort's original visibility.
    const visible=api.workflow_runs.filter(x=>
       typeof x.created_at==="string"&&Number.isFinite(Date.parse(x.created_at))&&
       Date.parse(x.created_at)<=checkMs);
    const candidate=decide({
      cron:rule,scheduledMs:checkMs,nowMs:checkMs,
      data:{workflow_runs:visible,total_count:visible.length}
    });
    const late=created>checkMs;
    rows.push({
      source_run_id:r.run_id,
      source_slot_utc:new Date(nominal).toISOString(),
      shadow_check_utc:new Date(checkMs).toISOString(),
      observed_action_created_utc:new Date(created).toISOString(),
      creation_lag_minutes:r.scheduled_creation_lag_minutes,
      final_sha_attested:r.durable_sha_lineage_verified===true,
      final_shard_count:r.sampled_original_shards_accepted,
      retrospective_worker_decision:candidate.reason,
      would_dispatch_under_reconstructed_available_run_page:candidate.dispatch===true,
      actual_source_run_created_after_check:late,
      potential_late_source_overlap:late&&candidate.dispatch===true,
      original_api_snapshot_at_check_recovered:false,
      actual_external_worker_trigger_proven:false,
    });
  }
  return {
    phase:"P1_RETROSPECTIVE_EXTERNAL_CRON_SHADOW_COMPARISON",
    active_source_shards:audit.active_completed_shards,
    evaluated_scheduled_runs:rows.length,
    severe_delayed_runs:rows.filter(x=>x.creation_lag_minutes>180).length,
    counterfactual_recovery_eligible_runs:rows.filter(x=>x.would_dispatch_under_reconstructed_available_run_page).length,
    possible_late_source_overlap_runs:rows.filter(x=>x.potential_late_source_overlap).length,
    proof_limitation:"RETROSPECTIVE_RUN_PAGE_NOT_AUTHENTICATED_TIME_OF_EACH_SHADOW_CHECK",
    actual_external_worker_trigger_proven:false,
    deploy_authorized:false,
    external_dispatch_enabled:false,
    extra_collection_started:false,
    safe_recommendation:"KEEP_WORKER_DISABLED_PENDING_TIME_OF_CHECK_SNAPSHOT_AND_DUPLICATE_LATE_RUN_GUARD",
    rows,
    trade_gate:"BLOCKED",orders:[],executable_candidates:[]
  };
}
if(import.meta.url===`file://${process.argv[1]}`){
  if(process.argv.length!==5)throw Error("usage: node shadow-audit.mjs AUDIT ACTIONS OUTPUT");
  const result=shadow(JSON.parse(readFileSync(process.argv[2],"utf8")),
                      JSON.parse(readFileSync(process.argv[3],"utf8")));
  mkdirSync(dirname(process.argv[4]),{recursive:true});
  writeFileSync(process.argv[4],JSON.stringify(result,null,2)+"\n");
  console.log("P1_EXTERNAL_SHADOW",JSON.stringify({
    evaluated:result.evaluated_scheduled_runs,
    late:result.severe_delayed_runs,
    counterfactual_recoveries:result.counterfactual_recovery_eligible_runs,
    possible_overlaps:result.possible_late_source_overlap_runs,
    gate:result.trade_gate
  }));
}
