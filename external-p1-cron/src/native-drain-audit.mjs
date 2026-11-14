// Read-only pre-cutover drain evidence audit. NEVER authorizes actual dispatch.
// GitHub scheduled runs may be CREATED long after nominal cron; an empty live
// queue alone does not establish old source schedule has drained.
import {nativeSchedulePresence} from "./index.mjs";
import {readFileSync,writeFileSync,mkdirSync} from "node:fs";
import {dirname} from "node:path";

export const PHASE="P1_NATIVE_SCHEDULE_DRAIN_READ_ONLY_PREFLIGHT";
export function assessDrain({source,sourceSha,runs,observationUtc,disabledSinceUtc=null}) {
  const reject=(reason,additional={})=>({
    phase:PHASE,state:"BLOCKED",reason,...additional,
    native_schedule_cutover_certified:false,
    old_source_run_drain_certified:false,
    external_dispatch_authorized:false,
    historical_PIT_verified:false,
    trade_gate:"BLOCKED",orders:[],executable_candidates:[]
  });
  if(typeof sourceSha!=="string" || !/^[0-9a-f]{40}$/.test(sourceSha))
    return reject("UNVERIFIED_WORKFLOW_SOURCE_SHA");
  const sourceState=nativeSchedulePresence(source);
  if(sourceState!=="ABSENT_IN_READ_MAIN_WORKFLOW")
    return reject(sourceState==="ENABLED"?"NATIVE_CRON_STILL_ENABLED":"NATIVE_SCHEDULE_SOURCE_UNVERIFIED",{sourceSha});
  if(!Number.isFinite(Date.parse(observationUtc)) ||
     new Date(observationUtc).toISOString()!==observationUtc)
    return reject("INVALID_OBSERVATION_TIMESTAMP");
  const now=Date.parse(observationUtc);
  if(typeof disabledSinceUtc!=="string" ||
     !Number.isFinite(Date.parse(disabledSinceUtc)) ||
     new Date(disabledSinceUtc).toISOString()!==disabledSinceUtc ||
     Date.parse(disabledSinceUtc)>now)
    return reject("NO_AUTHENTICATED_NATIVE_CRON_DISABLE_TIME",{sourceSha});
  const cutoff=Date.parse(disabledSinceUtc);
  if(now-cutoff<24*3600000)
    return reject("INSUFFICIENT_DRAIN_GRACE_24H",{sourceSha});
  if(!runs || !Array.isArray(runs.workflow_runs) ||
     !Number.isInteger(runs.total_count) ||
     runs.total_count!==runs.workflow_runs.length ||
     runs.workflow_runs.length===0 || runs.workflow_runs.length>100)
    return reject("INCOMPLETE_OR_INVALID_GITHUB_RUN_ROSTER",{sourceSha});
  let active=0,late=0,last=null;const ids=new Set();
  for(const r of runs.workflow_runs){
    if(!r || !Number.isSafeInteger(r.id) || r.id<=0 || ids.has(r.id) ||
       r.path!==".github/workflows/p1-fresh-vendor-roster.yml" ||
       r.head_branch!=="main" ||
       !["schedule","workflow_dispatch","push"].includes(r.event))
      return reject("UNTRUSTED_SOURCE_RUN_IDENTITY",{sourceSha});
    ids.add(r.id);
    const created=Date.parse(r.created_at);
    if(!Number.isFinite(created) || created>now+120000)
      return reject("INVALID_RUN_CREATED_AT",{sourceSha});
    if(last===null||created>last)last=created;
    if(!["completed","queued","in_progress","requested","waiting","pending"].includes(r.status))
      return reject("UNKNOWN_RUN_STATUS",{sourceSha});
    if(r.status!=="completed")active++;
    if(r.event==="schedule" && created>=cutoff)late++;
    if(r.status==="completed" &&
      !["success","failure","cancelled","timed_out","skipped","neutral","action_required","stale"].includes(r.conclusion))
      return reject("UNKNOWN_TERMINAL_RUN_CONCLUSION",{sourceSha});
  }
  if(active)return reject("P1_RUNS_STILL_ACTIVE_OR_QUEUED",{sourceSha,active});
  if(late)return reject("LATE_NATIVE_SCHEDULE_CREATED_AFTER_CUTOVER",{sourceSha,late});
  // No GitHub guarantee of maximum schedule creation delay exists. Even a
  // clear 24h observation cannot make an unconditional no-late-run promise.
  return reject("NO_HARD_UPPER_BOUND_FOR_GITHUB_SCHEDULE_CREATION",{sourceSha,
    observedClosedRuns:runs.workflow_runs.length,
    latestCreatedAtUtc:new Date(last).toISOString(),
    minimumGraceHours:24,
    currentObservationsConsistentWithDrain:true});
}
if(import.meta.url===`file://${process.argv[1]}`){
  if(process.argv.length!==6)throw Error("usage: node native-drain-audit.mjs WORKFLOW_SOURCE SHA ACTIONS_RUNS OUTPUT");
  const source=readFileSync(process.argv[2],"utf8");
  const sha=process.argv[3];
  const runs=JSON.parse(readFileSync(process.argv[4],"utf8"));
  const out=assessDrain({source,sourceSha:sha,runs,observationUtc:new Date().toISOString()});
  mkdirSync(dirname(process.argv[5]),{recursive:true});
  writeFileSync(process.argv[5],JSON.stringify(out,null,2)+"\n");
  console.log("P1_NATIVE_DRAIN_PREFLIGHT",JSON.stringify({reason:out.reason,authorized:false,trade_gate:out.trade_gate}));
}
