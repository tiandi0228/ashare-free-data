import test from "node:test";
import assert from "node:assert/strict";
import {decide,run,nativeSchedulePresence} from "../src/index.mjs";

const cron="25 1,2,4,6,8,10,12,14,16 * * 1-5";
const t=Date.parse("2026-11-05T02:25:00Z"); // Thursday 10:25 Beijing
const now=t;
const mk=(id,when,status="completed")=>({
  id,path:".github/workflows/p1-fresh-vendor-roster.yml",
  head_branch:"main",created_at:when,status
});
const history=(rows)=>({total_count:rows.length,workflow_runs:rows});
const previous=mk(101,"2026-11-05T00:20:00Z");
const approved=()=>decide({cron,scheduledMs:t,nowMs:now,
  data:history([previous])});

test("default is shadow-only, even when secret is connected; no network or dispatch",async()=>{
  const oldFetch=globalThis.fetch;
  let calls=0;
  try{
    globalThis.fetch=async()=>{calls++;throw Error("should never be reached");};
    for(const enabled of [undefined,"false","TRUE","1",true]){
      const r=await run(cron,t,t,{GITHUB_TOKEN:"connected-secret",
         P1_EXTERNAL_DISPATCH_ENABLED:enabled});
      assert.equal(r.dispatch,false);
      assert.equal(r.reason,"SHADOW_ONLY_DISPATCH_DISABLED");
      assert.equal(r.networkRequests,0);
      assert.equal(r.trade_gate,"BLOCKED");
    }
    assert.equal((await run(cron,t,t,{})).dispatch,false);
    assert.equal(calls,0);
  }finally{globalThis.fetch=oldFetch;}
});

test("bounded one-shard recovery admits only historical run gaps",()=>{
  const r=approved();
  assert.equal(r.dispatch,true);
  assert.equal(r.requestedShards,1);
  assert.equal(r.sourceSlot,"2026-11-05T09:10:00+08:00");
  assert.equal(r.markerPath,"recovery-dispatch-attempts/2026-11-05/0910.json");
});
test("no issue on queued, running, recent, unknown or untrusted run list",()=>{
  for(const status of ["queued","in_progress","waiting","pending","requested"]){
    const r=decide({cron,scheduledMs:t,nowMs:now,
      data:history([previous,mk(102,"2026-11-05T01:20:00Z",status)])});
    assert.equal(r.dispatch,false,status);
  }
  for(const rows of [
    [previous,mk(102,"2026-11-05T01:20:00Z")],
    [previous,previous],
    [mk(102,"2026-11-05T01:10:00Z")],
    [],
  ]){
    assert.equal(decide({cron,scheduledMs:t,nowMs:now,
      data:history(rows)}).dispatch,false);
  }
  assert.equal(decide({cron,scheduledMs:t,nowMs:now,
    data:history([{...previous,head_branch:"feature"}])}).dispatch,false);
});
test("reject delayed cron and malformed timings",()=>{
  for(const delta of [-20,16,100]){
    assert.equal(decide({cron,scheduledMs:t,nowMs:t+delta*60000,
      data:history([previous])}).dispatch,false);
  }
  assert.equal(decide({cron:"* * * * *",scheduledMs:t,nowMs:t,
    data:history([previous])}).dispatch,false);
  const weekend=Date.parse("2026-11-07T02:25:00Z");
  const w=decide({cron:"25 2,8,12,16 * * 6,0",scheduledMs:weekend,nowMs:weekend,
    data:history([mk(90,"2026-11-06T17:00:00Z")])});
  assert.equal(w.dispatch,true);
  assert.equal(w.sourceSlot,"2026-11-07T09:10:00+08:00");
});
test("real current main P1 schedule declaration detected",()=>{
 const yaml=[
   "name: P1 fresh Baostock mainboard roster observation (NO TRADES)",
   "on:",
   "  push:",
   "    branches: [main]",
   "  schedule:",
   "    - cron: '10 1 * * 1-5'",
   "  workflow_dispatch:",
   "    inputs: {}"
 ].join("\n")+"\n";
 assert.equal(nativeSchedulePresence(yaml),"ENABLED");
 assert.equal(nativeSchedulePresence(yaml.replace("  schedule:\n    - cron: '10 1 * * 1-5'\n","")),"ABSENT_IN_READ_MAIN_WORKFLOW");
 assert.equal(nativeSchedulePresence("on: [push, schedule]"),"UNVERIFIED");
 assert.equal(nativeSchedulePresence("random YAML"),"UNVERIFIED");
});
test("explicitly enabled Worker STILL refuses native schedule with no PUT or POST",async()=>{
 const prior=globalThis.fetch;
 const paths=[];
 try{
   globalThis.fetch=async(url)=>{
     paths.push(url);
     assert.ok(url.includes("/contents/.github/workflows/p1-fresh-vendor-roster.yml?ref=main"));
     const yaml="on:\n  schedule:\n    - cron: '10 1 * * 1-5'\n  workflow_dispatch:\n";
     return {ok:true,status:200,json:async()=>({
       path:".github/workflows/p1-fresh-vendor-roster.yml",
       type:"file",sha:"a".repeat(40),encoding:"base64",
       content:Buffer.from(yaml).toString("base64")
     })};
   };
   const out=await run(cron,t,t,{GITHUB_TOKEN:"test-token",P1_EXTERNAL_DISPATCH_ENABLED:"true"});
   assert.equal(out.dispatch,false);
   assert.equal(out.nativeScheduleState,"ENABLED");
   assert.equal(out.reason,"NATIVE_SCHEDULE_ACTIVE_OR_UNVERIFIED");
   assert.equal(paths.length,1);
 }finally{globalThis.fetch=prior;}
});
test("even absence of native schedule is not a certified drain",async()=>{
 const prior=globalThis.fetch;let calls=0;
 try{
   globalThis.fetch=async()=>{
     calls++;
     const yaml="on:\n  workflow_dispatch:\n";
     return {ok:true,json:async()=>({
       path:".github/workflows/p1-fresh-vendor-roster.yml",
       type:"file",sha:"b".repeat(40),encoding:"base64",
       content:Buffer.from(yaml).toString("base64")
     })};
   };
   const out=await run(cron,t,t,{GITHUB_TOKEN:"x",P1_EXTERNAL_DISPATCH_ENABLED:"true"});
   assert.equal(out.dispatch,false);
   assert.equal(out.reason,"SOURCE_RUN_DRAIN_NOT_AUTHENTICATED");
   assert.equal(calls,1);
 }finally{globalThis.fetch=prior;}
});
test("untrusted native schedule workflow bytes fail closed",async()=>{
 const prior=globalThis.fetch;
 try{
   globalThis.fetch=async()=>({ok:true,json:async()=>({
     path:".github/workflows/OTHER.yml",
     type:"file",sha:"c".repeat(40),encoding:"base64",content:""
   })});
   await assert.rejects(
     run(cron,t,t,{GITHUB_TOKEN:"x",P1_EXTERNAL_DISPATCH_ENABLED:"true"}),
     /NATIVE_SCHEDULE_SOURCE_NOT_ATTESTED/);
 }finally{globalThis.fetch=prior;}
});

test("three UTC rules uniquely cover all 58 weekly source slots including local midnight",()=>{
  const rules=[
    ["25 1,2,4,6,8,10,12,14,16 * * 1-5",[1,2,4,6,8,10,12,14,16],[1,2,3,4,5]],
    ["25 18 * * 0-4",[18],[0,1,2,3,4]],
    ["25 2,8,12,16 * * 6,0",[2,8,12,16],[6,0]],
  ];
  const utcStart=Date.parse("2026-11-01T00:00:00Z"); // Sunday
  const observed=new Map();
  const beijing=(ms)=>{
    const d=new Date(ms+8*3600000);
    return {weekday:d.getUTCDay(),hour:d.getUTCHours(),minute:d.getUTCMinutes(),
      day:d.toISOString().slice(0,10)};
  };
  for(let offset=0;offset<7;offset++){
    const dateMs=utcStart+offset*86400000;
    const day=new Date(dateMs).getUTCDay();
    for(const [rule,hours,weekdays] of rules){
      if(!weekdays.includes(day)) continue;
      for(const hour of hours){
        const scheduledMs=dateMs+hour*3600000+25*60000;
        const sourceMs=scheduledMs-75*60000;
        const source=beijing(sourceMs);
        const expected=source.weekday>0&&source.weekday<6
          ? [1,8,9,11,13,15,17,19,21,23] : [9,15,19,23];
        assert.equal(source.minute,10);
        assert.ok(expected.includes(source.hour),source.day+" "+source.hour);
        const key=source.day+"_"+source.hour;
        assert.ok(!observed.has(key),"duplicate recovery for "+key);
        observed.set(key,true);
        // If this is a real missed slot and metadata is verifiably fresh,
        // the schedule must pass the date/weekday admission checks.
        const former=mk(99,new Date(sourceMs-75*60000).toISOString());
        const result=decide({cron:rule,scheduledMs,nowMs:scheduledMs,
          data:history([former])});
        assert.equal(result.dispatch,true,JSON.stringify({rule,key,result}));
      }
    }
  }
  assert.equal(observed.size,58);
  assert.ok(observed.has("2026-11-02_1")); // Sunday UTC -> Mon Beijing 01:10
  assert.ok(observed.has("2026-11-06_23")); // Fri 23:10 -> Sat 00:25 recovery
  assert.ok(observed.has("2026-11-01_23")); // Sun 23:10 -> Mon 00:25 recovery
});
test("cron identity, weekday and UTC hour must match scheduledTime",()=>{
  const bad=decide({cron:"25 18 * * 0-4",scheduledMs:t,nowMs:t,
    data:history([previous])});
  assert.equal(bad.dispatch,false);
  const badWeekend=decide({cron:"25 2,8,12,16 * * 6,0",
    scheduledMs:t,nowMs:t,data:history([previous])});
  assert.equal(badWeekend.dispatch,false);
});
