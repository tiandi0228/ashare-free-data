import test from "node:test";
import assert from "node:assert/strict";
import {decide,run} from "../src/index.mjs";

const cron="25 2,6,10,14 * * 1-5";
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
  const w=decide({cron:"25 2,10 * * 6,0",scheduledMs:weekend,nowMs:weekend,
    data:history([mk(90,"2026-11-06T17:00:00Z")])});
  assert.equal(w.dispatch,true);
  assert.equal(w.sourceSlot,"2026-11-07T09:10:00+08:00");
});
test("404 create-only claim, readback, dispatch 204: accepted not completed",async()=>{
  const receipt=[];
  const calls=[];
  const oldFetch=globalThis.fetch;
  try{
    globalThis.fetch=async (url,opts)=>{
      calls.push({url,opts});
      if(url.includes("/actions/workflows/")&&url.includes("/runs?"))
        return {ok:true,status:200,json:async()=>history([previous])};
      if(url.includes("/contents/")&&(!opts.method||opts.method==="GET")){
        if(!receipt.length) return {ok:false,status:404};
        return {ok:true,status:200,json:async()=>({
          path:"recovery-dispatch-attempts/2026-11-05/0910.json",
          content:Buffer.from(receipt[0],"utf8").toString("base64")
        })};
      }
      if(opts.method==="PUT"){const b=JSON.parse(opts.body);
        assert.equal(b.branch,"research-intraday-snapshots");
        assert.equal(b.sha,undefined);
        receipt.push(Buffer.from(b.content,"base64").toString("utf8"));
        return {ok:true,status:201};}
      if(url.endsWith("/dispatches")){
        assert.deepEqual(JSON.parse(opts.body),{
          ref:"main",inputs:{shards_per_run:"1",recovery_token:""}
        });
        return {ok:true,status:204};
      }
      throw Error("unexpected "+url);
    };
    const r=await run(cron,t,t,{GITHUB_TOKEN:"test-token"});
    assert.equal(r.reason,"REQUEST_ACCEPTED_NOT_COLLECTION_VERIFIED");
    assert.equal(calls.filter(x=>x.url.endsWith("/dispatches")).length,1);
    assert.ok(receipt[0].includes('"trade_gate":"BLOCKED"'));
  } finally {globalThis.fetch=oldFetch;}
});
test("existing reserved slot forbids dispatch",async()=>{
  const oldFetch=globalThis.fetch;
  let posts=0;
  try{
    globalThis.fetch=async (url)=>{
      if(url.includes("/runs?")) return {ok:true,json:async()=>history([previous])};
      if(url.includes("/contents/")) return {status:200};
      posts++;throw Error("should not be reached");
    };
    const result=await run(cron,t,t,{GITHUB_TOKEN:"test-token"});
    assert.equal(result.reason,"SLOT_ALREADY_RESERVED");
    assert.equal(posts,0);
  }finally{globalThis.fetch=oldFetch;}
});
test("create race and unreadable marker both fail closed",async()=>{
  const oldFetch=globalThis.fetch;
  for(const code of [409,422,500]){
    let requests=0;
    try{
      globalThis.fetch=async (url,opts)=>{
        if(url.includes("/runs?")) return {ok:true,json:async()=>history([previous])};
        if(url.includes("/contents/")&&(!opts.method||opts.method==="GET"))
          return {status:404};
        if(opts.method==="PUT") return {status:code};
        requests++;throw Error("unexpected dispatch");
      };
      if(code===500) await assert.rejects(run(cron,t,t,{GITHUB_TOKEN:"t"}));
      else assert.equal((await run(cron,t,t,{GITHUB_TOKEN:"t"})).dispatch,false);
      assert.equal(requests,0);
    }finally{globalThis.fetch=oldFetch;}
  }
});
