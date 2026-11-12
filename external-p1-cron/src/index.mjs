// Independent, free-tier compatible GitHub P1 research recovery scheduler.
// NO HTTP handler, trading orders or fabricated shard completion.
// All times are UTC. Cron source slot is 75 minutes before Worker schedule.
export const REPO = "tiandi0228/ashare-free-data";
export const TARGET = "p1-fresh-vendor-roster.yml";
export const BRANCH = "research-intraday-snapshots";
// Three UTC rules cover all reviewed Beijing P1 source slots. Each check
// follows the source :10 slot by 75 minutes, including midnight rollover.
export const ALLOWED = new Set([
  "25 1,2,4,6,8,10,12,14,16 * * 1-5",
  "25 18 * * 0-4",
  "25 2,8,12,16 * * 6,0"
]);
const RULE_HOURS = new Map([
  ["25 1,2,4,6,8,10,12,14,16 * * 1-5",
    new Set([1,2,4,6,8,10,12,14,16])],
  ["25 18 * * 0-4", new Set([18])],
  ["25 2,8,12,16 * * 6,0", new Set([2,8,12,16])],
]);
const cronMatchesUTC = (rule, timestamp) => {
  const d = new Date(timestamp);
  const wd = d.getUTCDay();
  const hr = d.getUTCHours();
  const inRule = RULE_HOURS.get(rule)?.has(hr) && d.getUTCMinutes() === 25;
  if (!inRule) return false;
  if (rule === "25 18 * * 0-4") return wd >= 0 && wd <= 4;
  if (rule === "25 2,8,12,16 * * 6,0") return wd === 0 || wd === 6;
  return wd >= 1 && wd <= 5;
};
const MAX_RUNS = 100;

const beijingParts = (ms) => {
  const d = new Date(ms + 8 * 3600000);
  return {day: d.getUTCDay(), hour: d.getUTCHours(), minute: d.getUTCMinutes(),
    date: d.toISOString().slice(0, 10)};
};
const pad = (v) => String(v).padStart(2, "0");
const isMainRun = (x) => x && x.path === ".github/workflows/" + TARGET &&
  x.head_branch === "main";
const parseTimestamp = (s) => typeof s === "string" ? Date.parse(s) : NaN;

// Pure admission gate. GitHub list must cover the slot with one preceding run;
// a delayed source scheduled run must never be mistaken for missing proof.
export function decide({cron, scheduledMs, nowMs, data}) {
  const fail = (reason) => ({dispatch: false, reason});
  if (!ALLOWED.has(cron)) return fail("UNKNOWN_CRON");
  if (![scheduledMs, nowMs].every(Number.isFinite)) return fail("INVALID_TIME");
  const nominal = beijingParts(scheduledMs);
  const sourceMs = scheduledMs - 75 * 60000;
  const source = beijingParts(sourceMs);
  const weekday = source.day >= 1 && source.day <= 5;
  const validHours = weekday ? [1,8,9,11,13,15,17,19,21,23] : [9,15,19,23];
  if (!cronMatchesUTC(cron, scheduledMs) ||
      nominal.minute !== 25 || source.minute !== 10 ||
      !validHours.includes(source.hour)) {
    return fail("UNRECOGNIZED_SOURCE_SLOT");
  }
  const delta = (nowMs - sourceMs) / 60000;
  if (delta < 65 || delta > 90) return fail("OUTSIDE_65_90_MIN_SAFE_WINDOW");
  if (!data || !Number.isInteger(data.total_count) ||
      !Array.isArray(data.workflow_runs) || data.workflow_runs.length < 1 ||
      data.workflow_runs.length > MAX_RUNS ||
      data.total_count < data.workflow_runs.length) return fail("UNTRUSTED_RUN_COVERAGE");
  let earlier = false;
  let newest = -Infinity;
  const ids = new Set();
  for (const x of data.workflow_runs) {
    if (!isMainRun(x) || !Number.isSafeInteger(x.id) || x.id < 1 || ids.has(x.id))
      return fail("INVALID_OR_DUPLICATED_MAIN_RUN");
    ids.add(x.id);
    const ms = parseTimestamp(x.created_at);
    if (!Number.isFinite(ms) || ms > nowMs + 300000) return fail("INVALID_RUN_TIMESTAMP");
    newest = Math.max(newest, ms);
    if (ms < sourceMs - 120000) earlier = true;
    if (!["completed", "queued", "in_progress", "requested", "pending", "waiting"].includes(x.status))
      return fail("UNKNOWN_RUN_STATUS");
    if (x.status !== "completed") return fail("P1_RUN_ALREADY_ACTIVE");
    if (ms >= sourceMs - 120000) return fail("P1_RUN_ALREADY_STARTED_AFTER_SLOT");
  }
  if (!earlier || nowMs - newest > 86400000)
    return fail("RUN_HISTORY_NOT_FRESH_OR_NOT_COVERING_SLOT");
  const path = "recovery-dispatch-attempts/" + source.date + "/" +
    pad(source.hour) + "10.json";
  return {dispatch: true, reason: "ELIGIBLE_TO_RESERVE_ONE_ATTEMPT",
    sourceSlot: source.date + "T" + pad(source.hour) + ":10:00+08:00",
    markerPath: path, requestedShards: 1};
}

function api(token, path, opts = {}) {
  return fetch("https://api.github.com/repos/" + REPO + "/" + path, {
    ...opts, headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": "Bearer " + token,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "stockmate-p1-external-bounded-recovery",
      ...(opts.headers || {})
    }
  });
}
async function jsonResponse(response) {
  if (!response.ok) throw new Error("GITHUB_API_" + response.status);
  return response.json();
}
function base64(str) {
  // GitHub Contents API requires base64. ASCII-only audit marker by design.
  return btoa(str);
}
// Mutually exclusive scheduler ownership: an enabled native P1 schedule
// renders an independent dispatch unsafe even after manual Worker opt-in.
// This verifies the *live main-branch source*, not a cached documentation
// claim. Source read errors and unfamiliar workflow syntax fail closed.
// A separate cutover grace and source-run drain would still be required
// before any future deployment may be considered production-safe.
export function nativeSchedulePresence(source) {
  if(typeof source !== "string" || source.length > 200000 ||
     !/^on:\\s*$/m.test(source) ||
     !/^  workflow_dispatch:\\s*$/m.test(source)) return "UNVERIFIED";
  // Match a complete top-level (two-space indent) YAML schedule key, not
  // a comment, a run-name string or a shell code snippet.
  if(/^  schedule:\\s*$/m.test(source))return "ENABLED";
  // Refuse a different workflow event syntax rather than assume no cron.
  if(/^  ['"]?schedule['"]?\\s*:/m.test(source))return "UNVERIFIED";
  return "ABSENT_IN_READ_MAIN_WORKFLOW";
}
async function proveNativeScheduleAbsent(token) {
  const resp=await api(token,
    "contents/.github/workflows/" + TARGET + "?ref=main");
  const document=await jsonResponse(resp);
  if(document.path!==".github/workflows/"+TARGET ||
     document.type!=="file" || typeof document.sha!=="string" ||
     !/^[0-9a-f]{40}$/.test(document.sha) ||
     document.encoding!=="base64" || typeof document.content!=="string")
     throw new Error("NATIVE_SCHEDULE_SOURCE_NOT_ATTESTED");
  let decoded;
  try{decoded=atob(document.content.replace(/\\s/g,""));}
  catch{throw new Error("NATIVE_SCHEDULE_SOURCE_NOT_DECODABLE");}
  const state=nativeSchedulePresence(decoded);
  return {state,sha:document.sha};
}
export async function run(cron, scheduledMs, nowMs, env) {
  // Deployment alone MUST NOT turn an optional scheduler into a writer.
  // Even a valid GitHub token and scheduled cron leave the Worker inert until
  // an explicit, separately reviewed production configuration opts in.
  // Safe default requires no GitHub API call, marker write or dispatch.
  if (!env || env.P1_EXTERNAL_DISPATCH_ENABLED !== "true")
    return {dispatch:false,reason:"SHADOW_ONLY_DISPATCH_DISABLED",
      networkRequests:0,sourceMutationAuthorized:false,
      trade_gate:"BLOCKED"};
  if (typeof env.GITHUB_TOKEN !== "string" || !env.GITHUB_TOKEN)
    throw new Error("MISSING_GITHUB_TOKEN");
  const native=await proveNativeScheduleAbsent(env.GITHUB_TOKEN);
  if(native.state!=="ABSENT_IN_READ_MAIN_WORKFLOW")
    return {dispatch:false,reason:"NATIVE_SCHEDULE_ACTIVE_OR_UNVERIFIED",
      nativeScheduleState:native.state,sourceWorkflowSha:native.sha,
      noMarkerWritten:true,trade_gate:"BLOCKED"};
  // Removing a native cron can leave previously queued scheduled jobs.
  // The current external fallback still does NOT have an independently
  // certified drain/wait period, so fail closed rather than risk a late
  // original runner overlapping the recovery request.
  return {dispatch:false,reason:"SOURCE_RUN_DRAIN_NOT_AUTHENTICATED",
    nativeScheduleState:native.state,sourceWorkflowSha:native.sha,
    noMarkerWritten:true,trade_gate:"BLOCKED"};
  // Fetch the exact P1 workflow runs, not the generic repository run stream.
  const runs = await jsonResponse(await api(env.GITHUB_TOKEN,
    "actions/workflows/" + TARGET + "/runs?per_page=100"));
  const decision = decide({cron, scheduledMs, nowMs, data: runs});
  if (!decision.dispatch) return decision;
  const marker = decision.markerPath;
  const prior = await api(env.GITHUB_TOKEN,
    "contents/" + marker + "?ref=" + encodeURIComponent(BRANCH));
  if (prior.status === 200) return {dispatch:false,reason:"SLOT_ALREADY_RESERVED"};
  if (prior.status !== 404) throw new Error("MARKER_READ_FAILED_" + prior.status);
  const receipt = JSON.stringify({
    phase:"P1_EXTERNAL_SINGLE_SHARD_DISPATCH_ATTEMPT",
    slot:decision.sourceSlot, state:"DISPATCH_REQUEST_RESERVED_NOT_COMPLETED",
    requested_shards:1, trade_gate:"BLOCKED",
    historical_PIT_verified:false, orders:[], executable_candidates:[]
  }) + "\n";
  const created = await api(env.GITHUB_TOKEN, "contents/" + marker, {
    method:"PUT", body:JSON.stringify({branch:BRANCH,
      message:"audit(p1): reserve external one-shard recovery request [NO TRADES]",
      content:base64(receipt)})
  });
  // Create-only conflict is a safe loss in a race, never a reason to retry.
  if (created.status === 409 || created.status === 422)
    return {dispatch:false,reason:"ATOMIC_SLOT_RESERVATION_LOST"};
  if (created.status !== 201) throw new Error("MARKER_CREATE_FAILED_" + created.status);
  const readback = await jsonResponse(await api(env.GITHUB_TOKEN,
    "contents/" + marker + "?ref=" + encodeURIComponent(BRANCH)));
  if (readback.path !== marker || atob(readback.content.replace(/\s/g,"")) !== receipt)
    throw new Error("MARKER_READBACK_NOT_VERIFIED_NO_DISPATCH");
  // Never retry a failed or uncertain POST; the marker prevents later retries.
  const resp = await api(env.GITHUB_TOKEN,
    "actions/workflows/" + TARGET + "/dispatches", {
      method:"POST", body:JSON.stringify({ref:"main",
        inputs:{shards_per_run:"1",recovery_token:""}})
    });
  if (resp.status !== 204)
    throw new Error("DISPATCH_OUTCOME_UNKNOWN_DO_NOT_RETRY_" + resp.status);
  return {dispatch:true,reason:"REQUEST_ACCEPTED_NOT_COLLECTION_VERIFIED",
    sourceSlot:decision.sourceSlot};
}

export default {
  async scheduled(controller, env) {
    const result = await run(controller.cron, controller.scheduledTime, Date.now(), env);
    console.log(JSON.stringify(result));
  }
};
