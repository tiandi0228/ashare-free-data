# P1 external watchdog — deployment is OPTIONAL and NOT ACTIVE yet

This independent Cloudflare Workers Cron Trigger is a free-tier-compatible
**research-only, non-dispatching** audit prototype for the existing GitHub P1 workflow.
It does not collect data, place orders, certify PIT, or prove completion.

**SAFE DEFAULT (2026-11-12): deployment alone does NOT dispatch.** The Worker
now refuses even to query GitHub without the exact explicit environment
variable `P1_EXTERNAL_DISPATCH_ENABLED=true` (string `"true"`). A token,
Cron Trigger and successful deployment do not enable recovery. Do not set
that flag as part of a routine install: it requires a separate reviewed
authorization, a time-of-check race assessment and an approved rollback plan.
The historical GitHub scheduled source can be created >3 hours late, so a
+75-minute recovery might race with a legitimate future source job. **The
current Worker is therefore strictly non-dispatching even if the opt-in string
is set.** It checks the live `main` P1 workflow source read-only; when a native
schedule exists it blocks. When no native schedule exists it still blocks
until independently authenticated queued-source drain and a separate cutover
contract are implemented. No marker PUT or workflow_dispatch exists in this
revision's reachable Worker path.
A GitHub API 204 only confirms **a request was accepted**.

## Why
GitHub Actions schedule receipts for 2026-11-05 recorded
382.5 and 401.8 minute run-creation delays. This external scheduler can
check for a missing P1 source run independently; it does not eliminate
Cloudflare's own scheduling/availability uncertainty.

## Deployment (requires owner's Cloudflare account and explicit setup)
1. Use an existing Cloudflare Workers Free account. Check current free
   allowances and permissions; this code uses three Cron Triggers. Workers Free currently allows up to five Cron Triggers **per account**, so check other Workers before deploying.
2. No production connection or deployment is needed for the current phase.
   For optional read-only experimentation, scope a fine-grained GitHub token
   to this repository with **Contents: read** only. Do not grant write
   permissions for this non-dispatching version.
   Do not use a classic broad `repo` PAT and never commit or paste the token.
3. Only after explicitly approving a separate read-only deployment, from this directory run:
   ```sh
   npm install --no-save wrangler@4
   npx wrangler login
   npx wrangler secret put GITHUB_TOKEN
   npx wrangler deploy
   ```
   The secret command prompts locally. `workers_dev = false` intentionally
   provides no publicly accessible HTTP handler.
4. Inspect Cloudflare Cron Trigger logs, the GitHub P1 workflow run, its
   independent source provenance, and the exact frozen-epoch durable
   `evidence/checkpoints/<source_sha256>.json` before claiming growth.

## Fixed limits and fail-closed behavior
- Three UTC Cron expressions cover **every approved P1 source slot**,
  10 weekdays and 4 weekends (58 opportunities/week). Each check is
  75 minutes after its source :10 slot. The 23:10 Beijing source is
  checked at 00:25 **the following local day**; the Mon 01:10 source
  is checked at 02:25 Monday Beijing (18:25 UTC Sunday).
- Only the real clock 65–90 minutes after a matching source slot is eligible.
- Requires a fresh, valid, same-workflow GitHub run list that covers the slot,
  no active/queued run and no P1 run begun at or after the watched slot.
- Checks the existing `research-intraday-snapshots` branch's
  `recovery-dispatch-attempts/YYYY-MM-DD/HH10.json`; reserves it create-only,
  then independently reads back the exact bytes **before** dispatching.
- On any conflicting reservation or uncertain API POST, **no retries** for
  that slot. Concurrent independent schedulers may race, but GitHub's
  create-only reservation means only the confirmed winner dispatches.
- Requests **one shard** via `workflow_dispatch` on `main`, using an empty
  optional recovery token (not a synthetic claim of internal GitHub origin).
  Existing P1 Actions concurrency serializes workers and immutable ledger
  reconciliation prevents accepting duplicate original shard evidence.
- No API credentials in source, no orders, no trading gate change. If
  Cloudflare credentials or API access are unavailable, leave this disabled.
- Historical PIT certification remains false and `trade_gate=BLOCKED`.

## Tests
Run `node --test tests/worker.test.mjs tests/shadow-audit.test.mjs` from this directory. The shadow audit executes the real admission logic against reconstructed snapshots without fetching credentials or dispatching.
Node's native test runner requires no paid dependencies.

**Important:** This repository change only provides runnable source and a CI
verification suite. It does not enable or deploy a Cloudflare Worker.
