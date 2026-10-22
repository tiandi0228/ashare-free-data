# ashare-free-data — Public, FREE, research-only

Isolated public market-data **research** workflow. The private repository
`tiandi0228/scripts`, personal holdings, trading strategies, secrets and
historical Git commits have **not** been copied here.

## Verified research-only milestones (2026-10-21)

| Milestone | GitHub Actions run | Actual result |
|---|---|---|
| Baostock 3 securities / 2 calendar years | [#39571589234](https://github.com/tiandi0228/ashare-free-data/actions/runs/39571589234) | SUCCESS: 3 × 485 rows |
| Baostock first eight current securities | [#39572697952](https://github.com/tiandi0228/ashare-free-data/actions/runs/39572697952) | SUCCESS: 8 × 485, including 10 suspended rows for sh.603019 |
| Baostock second eight current securities | [#39573265839](https://github.com/tiandi0228/ashare-free-data/actions/runs/39573265839) | SUCCESS: 8 × 485 rows |
| Independently validate original-source bytes from both runs | [#39573806984](https://github.com/tiandi0228/ashare-free-data/actions/runs/39573806984) | SUCCESS: 16 issuer originals, 7,760 rows; 7,750 trade-status=1, 10 trade-status=0 |
| Baostock historical vendor roster for 2025-05-26 and 2026-10-20 | [#39574658518](https://github.com/tiandi0228/ashare-free-data/actions/runs/39574658518) | **BLOCKED:** vendor login rejected, **zero** real roster queries |
| Offline vendor-roster validation and fail-closed tests | [#39575055183](https://github.com/tiandi0228/ashare-free-data/actions/runs/39575055183) | SUCCESS: 22 offline tests, zero market queries |

### 2026-10-21: free Baostock listing lifecycle candidate (retrospective, NOT certified PIT)

[One-off source verification #39576085424](https://github.com/tiandi0228/ashare-free-data/actions/runs/39576085424) **SUCCESS**: 27 unit tests, one source login, one `query_stock_basic()` call, 9,018 original security records; 3,489 Shanghai/Shenzhen mainboard-prefix stock lifecycle records (of these, 294 marked delisted as of data capture). Retrospective IPO/delist intervals suggest **3,181 candidates on 2025-05-26** (including 32 later delisted names) and **3,195 candidates on 2026-10-20**. Data source and response checksums are recorded in [dated metadata](reports/p1_vendor_lifecycle_20261021.json).

**Do not equate** 3,195 third-party retrospective listing candidates with the separate private-repo 3,052 current-mainboard frozen research pool. Raw numeric difference is 143 but data-source and inclusion-policy equivalence has **not** been established. Issuer life dates lack publisher signature, historical ST status, authoritative trading halts, as-of revisions, and delist/IPO boundary semantics. Vendor records can have hindsight contamination. They are **not** an official point-in-time tradable historical universe. The original stock-basic CSV bytes were intentionally **not redistributed** publicly; durable SHA metadata does not preserve reconstructible original contents. Network workflow is now **manual-only** to protect public provider limits.

**Important:** 16 stock codes were manually frozen for a limited capacity
pilot, **not** reconstructed from historical official exchange membership.
The two-year range in the successful limited study is
2024-10-21 through 2026-10-20. `sh.603019` has 485 source rows of
which 475 have tradeStatus=1 and ten have tradeStatus=0. Do not count
suspended placeholder rows as tradeable bars.

[Durable public source SHA metadata](reports/p1_pilot_16_source_digests_20261021.json)
has been committed without republishing raw CSV source bytes. Original
CSV artifacts expire under GitHub retention rules; the metadata digests
alone cannot reconstruct expired source files.

## Current safety posture

- **No paid APIs, server purchases, broker connectivity or live orders.**
  Research `trade_gate=BLOCKED`, `orders=[]`,
  `executable_candidates=[]`.
- Cloud Runner previously downloaded 16 stocks using a limited Baostock
  client. Repeated successful tests do not imply unlimited Baostock
  reliability; latest two-date roster probe **failed on login**.
- Historical membership, dates, names and ST markers obtained from
  retrospective third-party vendor endpoints are *not* authenticated
  contemporaneous exchange snapshots.
- The dated Baostock roster workflow remains **manual-only** until
  network access reliability, permitted source usage, historical metadata
  and archive policy are verified. No unattended whole-market crawling.
- Earlier Eastmoney batch runs encountered ConnectionError; its routine
  push triggers were disabled to avoid waste.
- Only bounded pilot probes and offline unit tests run in GitHub Actions.
  Public Actions are still subject to provider acceptable-use restrictions.

### 2026-10-21: Official SSE event chronology and PIT acceptance

Exchange notice [2026-05-22 termination decision](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260522_10819392.shtml) for 600421 is distinct from the [2026-06-22 notice announcing actual removal on 2026-06-26](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260622_10823158.shtml). Do not use the termination decision date as the effective delisting date.

The independent two-document original-HTML/SHA pilot [#39578232761](https://github.com/tiandi0228/ashare-free-data/actions/runs/39578232761) **FAILED**: the public GitHub Actions runner got URL errors from both official pages. Original exchange bytes and SHA were NOT obtained; the workflow is now manual-only. Offline event chronology and tamper guards passed, but this is not an authenticated whole-market state.

The [independent offline source-digest PIT gate #39578658808](https://github.com/tiandi0228/ashare-free-data/actions/runs/39578658808) **SUCCEEDED with 42 unit tests**. It reconciles the Baostock 9,018-row lifecycle source receipt and 16-issuer source SHA metadata, rejects hindsight, incomplete historical ST/halt/delist evidence and mismatched 3,195 vs 3,052 universe scope. Both historical dates remain **trade_gate=BLOCKED**. Durable [gate report](reports/p1_p3_pit_gate_20261021.json) contains SHA receipts and metadata, not reconstructible original CSV files.

### 2026-10-21: 600421 CNINFO statutory issuer PDF cloud-source evidence

Independent CNINFO disclosure PDF [source](https://static.cninfo.com.cn/finalpage/2026-06-19/1225377517.PDF) was **successfully retrieved by the public GitHub Runner** in [#39579302851](https://github.com/tiandi0228/ashare-free-data/actions/runs/39579302851), unlike the two official SSE website URLs that failed with URLError on the earlier Runner. One HTTPS request, 109,614 source bytes, three readable PDF pages and SHA-256 `6e43f458ee70b11dc5ab7331c2d67dee62dc26fa2121e138a2c93ef71c65409f`. 47 offline tests passed.

This issuer disclosure mentions **estimated last trading day 2026-06-22**, not the exchange's independently verified actual delisting date. SSE's [2026-06-22 announcement](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260622_10823158.shtml) says actual removal 2026-06-26; the GitHub Runner **did not** obtain this SSE page's raw bytes or signed publisher evidence. CNINFO PDF is one issuer source, not complete historical ST/delisting, official PIT universe or trading permission. Only public source SHA metadata is committed in [PDF research receipt](reports/p3_cninfo_600421_disclosure_pdf_20261021.json); original PDF is not redistributed here, and the hash is not a reconstructible archive. PDF online-probe workflow is now manual-only. No paid calls or orders, trade_gate BLOCKED.

### 2026-10-21: two independently captured issuer risk PDFs

Real source PDFs from 600421 were separately retrieved on GitHub **Public** Actions using only free standard runners:
- [2026-05-23 early issuer resumption / delisting-period PDF](https://static.cninfo.com.cn/finalpage/2026-05-23/1225327963.PDF): [real run #39580585146](https://github.com/tiandi0228/ashare-free-data/actions/runs/39580585146), 244,242 bytes, three pages, SHA-256 `ef9b9113b2a51ca718e786de0613860351f0c8056916e7decb5a010da7acaff8`. The notice states resumption scheduled for **2026-06-01**, not independently verified tradability.
- [2026-06-19 issuer risk notice PDF](https://static.cninfo.com.cn/finalpage/2026-06-19/1225377517.PDF): [real run #39579302851](https://github.com/tiandi0228/ashare-free-data/actions/runs/39579302851), 109,614 bytes, three pages, SHA-256 `6e43f458ee70b11dc5ab7331c2d67dee62dc26fa2121e138a2c93ef71c65409f`. The notice says **expected final trading day 2026-06-22**, NOT exchange-verified actual delisting date.

[Chronological independent offline audit #39581101776](https://github.com/tiandi0228/ashare-free-data/actions/runs/39581101776) **SUCCESS with 70/70 tests**, seven explicitly frozen decision dates from May 22 to June 26 all QUARANTINED; original-exchange notice PDF/HTML was not fetched on Runner, precise historical publication timestamps not authenticated, complete historical ST/halt/delist universe unknown. [Permanent digest-only event-chain audit](reports/p3_600421_two_pdf_event_chain_20261021.json) and 30-day Artifact `12336735597` (expiry 2026-11-20). Hashes cannot reconstruct missing original PDF bytes and do not certify historical issuer state. `trade_gate=BLOCKED`, no orders or paid calls.

### 2026-10-21: Free provider substitution and 3%-of-position risk test

Independent source-capability routing now selects **Baostock** for small research-only historical price/lifecycle tasks and **CNINFO public issuer PDFs** for confirmed positive risk notices. Official SSE/SZSE per-session full-market status/membership (historical ST, halts and delistings) has **NO VERIFIED FREE AUTHENTICATED REPLACEMENT**. A news page, static PDF or retrospective vendor list may NOT fill this specific requirement. The fallback selector rejects falsified receipts, paid fallback, and accidental trade promotion.

**Policy regression identified:** the older PRIVATE P4 synthetic calculator uses 3% of an 8,000 CNY account as its *per-stock stop risk* (CNY 240). The user's frozen position policy is instead **3% of each stock's purchase notional**, including buy/sell commissions, stamp, transfer fees and slippage already reflected once in assumed actual fill prices. A public **independent synthetic audit** with 400 shares at CNY 10 and an assumed CNY 9.50 stop yields CNY 211.98 fee-inclusive modeled loss vs an eligible **CNY 120** notional-based budget. Therefore this scenario must FAIL even though it passes the older CNY 240 account-denominator budget. Synthetic assumed fills never guarantee actual loss limits in gaps, suspensions or locked limit days.

[Real CI #39584957755](https://github.com/tiandi0228/ashare-free-data/actions/runs/39584957755) **SUCCESS, 85 offline tests**. Source router `collector/free_source_fallback_router.py`, numeric pilot `collector/p4_position_notional_guard.py`, regression tests and [durable report](reports/free_fallback_p4_notional_20261021.json). **This does not change the PRIVATE P4 model yet**. Private model and P3 issuer authentication still need separate integration, validation and signoff. `trade_gate=BLOCKED`, no orders, zero paid APIs.

### 2026-10-21: delisted issuer original history and 24-source coverage (FREE, RESEARCH ONLY)

**Real new eight-issuer source** [#39589103403](https://github.com/tiandi0228/ashare-free-data/actions/runs/39589103403) succeeded on a public Runner (one Baostock login and eight issuer-history queries): seven active Shanghai/Shenzhen mainboard issuers each returned **485** source sessions, and the historically delisted `sh.600421` returned **408** source rows (378 with vendor tradeStatus=1 and **30** vendor suspended placeholders). The source's final *tradeStatus=1* row for `600421` is **2026-06-22**, whereas the final CSV row is **2026-06-25** and 2026-06-23 through June 25 are suspended placeholders. Thus the last data row must never be used as the final trading date. This is third-party trade status, not original exchange-signed PIT provenance.

Independent no-provider-request original ZIP/CSV/SHA replay [#39589886891](https://github.com/tiandi0228/ashare-free-data/actions/runs/39589886891) **SUCCESS, 94 offline tests**: 8 original CSV hashes matched the quality receipt, total **3,803** source rows, **3,773** vendor status=1 and **30** vendor status=0. [Permanent SHA-only receipt](reports/p1_delisted_8_source_digests_20261021.json). Original data Artifact `12340239649` expires **2026-11-04**; replay audit Artifact `12341690315` expires **2026-11-20**.

Combining the previously validated 16-issuer sources with these *disjoint* eight issuer codes, the verified research subset is **24 issuers, 11,563 original rows, 11,523 vendor status=1 and 40 vendor status=0**. [Offline combined-gate #39590598008](https://github.com/tiandi0228/ashare-free-data/actions/runs/39590598008) **SUCCESS with 100/100 tests**, derived Artifact `12342725142` (expires **2026-11-20**), durable [combined SHA-only source audit](reports/p1_research_24_coverage_20261021.json). First CI attempt failed due to a regression test accidentally mutating the wrong JSON level, not a bypassed production gate; the corrected test passed.

**Safety boundary:** these 24 purposively selected issuer histories do not prove full Shanghai/Shenzhen mainboard coverage, authoritative historical point-in-time membership, historical ST/halts/delist completeness, or real P4 walk-forward/OOS performance. Original source bytes are *not* permanently available from SHA-only Git metadata; respect provider licensing and Artifact expiration. Source audit success **never unlocks** `trade_gate=BLOCKED`, candidate lists or orders. No data source was purchased; private `tiandi0228/scripts` Actions were not triggered.

### 2026-10-21: free historical vendor ST and halt labels, original CSV independently replayed (P3 NOT CERTIFIED)

Beneath the original 24 stock-price research pilot, we also tested Baostock's **documented** daily `isST` and `tradestatus` fields for **two strictly scoped issuers**, `sh.600421` and `sh.603019` over **2025-05-20 through 2026-06-25**, without reclassifying them as exchange historical PIT:

- Real [vendor source capture #39602222641](https://github.com/tiandi0228/ashare-free-data/actions/runs/39602222641) **SUCCESS**: each issuer 268 original day/status rows; `sh.600421` has 250 vendor isST=1, 18 vendor isST=0, and 27 vendor suspended days in this window; `sh.603019` has 0 isST=1, 268 isST=0, and 10 vendor suspended days. All 536 source rows had an explicit isST field; no provider-paid API, at most 2 logical issuer queries. The `600421` expected final trading-status=1 2026-06-22 followed by suspended rows June 23–25, and known halted `603019` 2025-05-26 were validated against earlier vendor cases, **not exchange originals**.
- Independent real original CSV and SHA-256 [replay #39602931290](https://github.com/tiandi0228/ashare-free-data/actions/runs/39602931290) **SUCCESS with 111 offline tests**; all issuer source bytes/dates/statuses independently matched the original frozen source receipt, with zero fresh market requests. Permanent [P3 vendor ST SHA-only report](reports/p3_two_issuer_vendor_st_replay_20261021.json). Original CSV source Artifact `12346189195` expires **2026-11-04**, replay JSON Artifact `12347785076` expires **2026-11-20**. Both network and replay workflows are now **manual-only**, not recurring automatic queries.
- Upstream provider docs describe `isST` as a 0/1 **vendor historical daily data field**, not an original authenticated SSE/SZSE status announcement. Retroactive vendor revisions and historical publication times have **not** been established; full-market historical ST, suspension, delisting, corporate-action adjustment and source-licensed durable replay are still absent. `trade_gate=BLOCKED`, `orders=[]`, `executable_candidates=[]`.

GitHub's own public Actions Artifact retention cap is **90 days**, not permanent; merely increasing retention would not fix original data governance, and stored artifacts/logs can count toward billable storage. We avoid claiming a permanent free cloud data warehouse or redistributing vendor CSVs publicly without confirmed data rights.

### 2026-10-21: free replay retention and conditional byte-identical re-acquisition (research only)

Four source-original GitHub Actions Artifacts from **three historical bar batches and one two-issuer ST-status batch** were inspected using GitHub's live Actions API. All four originals still existed as of 2026-10-21T13:08Z, but **all expire on 2026-11-04**; public Action retention is bounded to 90 days, even if the workflow or SHA-only report lives longer. The lifecycle 9,018-row original and two regulatory issuer PDFs are *not* preserved as reconstructible bytes in this repository. Source SHA metadata cannot replace original bytes.

- Implemented `collector/source_retention_gate.py` with a live-source inventory, tamper/missing/expired-source rejection and explicit prohibition on equating temporary Artifacts or public GitHub Releases with a licensed permanent vendor archive. [Real public CI #39605369103](https://github.com/tiandi0228/ashare-free-data/actions/runs/39605369103) **SUCCESS, 119 offline tests**; verified 4/4 Artifacts live, earliest expiry about **13.82 days** ahead at audit time, formal persistent-replay gate **BLOCKED**. Frozen [live provenance inventory](reports/source_artifact_inventory_20261021.json) is a dated snapshot, not evergreen status.
- **Alternative strictly research-only free recovery route:** `collector/reacquire_source_digest.py` requests *at most two known symbols* from Baostock with original dates/fields/adjustment settings and compares newly observed byte-level SHA-256 with independently audited earlier source digests. [Real public CI #39606036344](https://github.com/tiandi0228/ashare-free-data/actions/runs/39606036344) **SUCCESS, 124 offline tests, two real provider requests:** delisted `sh.600421` **408/408 rows SHA equal** and `sh.600000` **485/485 rows SHA equal**. Durable [source comparison report](reports/p1_two_original_sources_reacquire_20261021.json) stores only digests and counts; original source CSV bytes were **not** republished or durably archived. The workflow was returned to **manual-only**.
- **This is not a certified archival solution:** Provider history may change, source APIs can fail, historical as-of release timestamps and official SSE/SZSE ST/halt/delist history remain unauthenticated. The open-source client license does **not** establish the rights to republish underlying financial market data. GitHub Releases could retain publication assets beyond temporary Actions expiry, but raw vendor-data redistribution and retention rights **must be independently reviewed before any upload**. If rights or a legitimate user-controlled private archive cannot be established, fail closed instead of claiming full P1/P3 or trade readiness. No paid provider, customer holdings, private strategy code or market orders were used.

### 2026-10-21: Entire frozen 24-issuer sample re-acquired byte-for-byte without raw redistribution

A free, bounded **on-demand conditional recovery mechanism** was added in `collector/reacquire_24_pilot.py` and independently audited by `collector/audit_24_reacquisition.py`. The original limited research universe is explicitly frozen at **24 issuer identifiers**, split into **three distinct 8-issuer batches**. Provider queries use identical original `Baostock` date range, field order, daily frequency and non-adjusted `adjustflag=3`. Each issuer's newly retrieved original-source CSV encoding and SHA-256 is compared against the SHA previously verified from original-byte cloud Artifacts. Any unknown issuer, missing result, source revision, byte mismatch, changed row count or fake trade/PIT status is rejected; original vendor CSV bytes are **not published or archived**.

- [First real trial: batch 2, Actions #39610601436](https://github.com/tiandi0228/ashare-free-data/actions/runs/39610601436) **SUCCESS**: 8 of 8 SHA-identical histories, **3,803** source rows including delisted `sh.600421`, 132 offline tests; report [batch 2](reports/p1_reacquire_8_of_24_batch_2_20261021.json).
- [Second real trial: batches 0 and 1, Actions #39611226852](https://github.com/tiandi0228/ashare-free-data/actions/runs/39611226852) **SUCCESS**: 16 of 16 SHA-identical histories, **7,760** source rows, two separately capped 8-query cycles, 132 offline tests; report [batches 0–1](reports/p1_reacquire_16_batches_01_20261021.json).
- [Independent cross-run public CI #39611942089](https://github.com/tiandi0228/ashare-free-data/actions/runs/39611942089) **SUCCESS with 140/140 offline tests**. All **24** historical source identities and **11,563** rows matched exactly *as observed in these three current batches*. Permanent [24/24 digest-only acceptance receipt](reports/p1_24_sha_recovery_verified_20261021.json) records this scope, test result and strictly `trade_gate=BLOCKED`.
- Both network trial workflows were returned to **`workflow_dispatch` only** after exactly one one-off cloud run each, to prevent repeated source calls and avoid unnecessary GitHub Action emails. Neither original vendor CSV nor private strategy data was committed to this public repository.

**Critical limits unchanged:** Exact bytes could be reacquired on **this test date**; provider revisions, downtime and data redistribution/long-term private archival rights remain unverified. GitHub original source Artifacts expire **2026-11-04**. A SHA-only receipt cannot reconstitute original bytes after expiry, so this is **not guaranteed permanent storage**. No verified official historical SSE/SZSE market-wide point-in-time issuer membership, historical ST/halts/delist completeness, announcement release timestamps, or genuine P4 walk-forward/out-of-sample validation exists. The 24-issuer sample is **not** the full roughly 3,000+ historical mainboard universe. No claim of executable recommendation or live-trade eligibility is permitted.

### 2026-10-21: two real dated historical vendor security rosters, source replay and survivorship warning

The earlier one-login/two-date Baostock `query_all_stock(day)` probe had once failed at login, but the bounded retry was **actually verified** in [source capture #39613467121](https://github.com/tiandi0228/ashare-free-data/actions/runs/39613467121), **SUCCESS**. We acquired real vendor original CSVs for **2025-05-26** (all 6,825 vendor securities, 3,181 provisional mainboard-code matches; vendor active 3,163, suspended 18, ST/*ST-name 149) and **2026-10-20** (all 7,440; provisional mainboard-code 3,195; active 3,191, suspended 4, ST/*ST-name 143). Frozen mainboard prefixes `sh.60[0-5]xxx` and `sz.00[0-3]xxx` **do not constitute an exchange-certified board membership definition**. The known `sh.603019` vendor halt on 2025-05-26 matched prior limited source evidence.

The authentic raw original 5-file Artifact `12350373792` expires **2026-11-04**. Independent [original-file audit #39614404688](https://github.com/tiandi0228/ashare-free-data/actions/runs/39614404688) **SUCCESS, 147 offline tests**: checks all SHA-256 hashes, full input row counts, filtered source data reproduction, names, status columns and known halt example, without new market calls. [Permanent original SHA receipt](reports/p1_two_real_dated_vendor_rosters_20261021.json) has no recoverable raw vendor bytes.

A further [read-only member-difference audit #39615039127](https://github.com/tiandi0228/ashare-free-data/actions/runs/39615039127) **SUCCESS, 154 offline tests**, computes the difference between these two exact original SHA-verified dated vendor snapshots: **3,149 codes in both**, **32 in 2025 only**, **46 in 2026 only**, **3,227 unique across the two dates**. `sh.600421` was in the early vendor snapshot but absent from the late. Of common codes, vendor tradeStatus transitions were `0→0: 0`, `0→1: 7`, `1→0: 4`, `1→1: 3,138`. These are *only two retrospective vendor date observations*, **not** authoritative IPO/delisting event counts, no authenticated as-of release timestamps, and not a full per-day historic stock pool. If one were to use only the 2026 date list for 2025 research, at least **32 early-only observed codes would be omitted**, a clear survivorship-bias hazard. [Permanent metadata/digest-only delta](reports/p1_vendor_two_dated_membership_delta_20261021.json), Artifact `12351618848` expires **2026-11-20**.

Both newly used workflows were returned to **manual-only** immediately after a successful bounded execution. **Formal blocks are unchanged:** original vendor archive expiry, legal storage/data-rights review, authoritative historical daily issuer/ST/halt/delist status, source publication instants, coverage of all daily histories, actual P4 OOS. `trade_gate=BLOCKED`, candidates/orders remain empty; no fees or private repository CI were used.

### 2026-10-22: bounded eight more *early-only vendor roster* historical bar sources

After original Baostock two-date roster source capture [#39613467121](https://github.com/tiandi0228/ashare-free-data/actions/runs/39613467121) and independent original CSV replay [#39614404688](https://github.com/tiandi0228/ashare-free-data/actions/runs/39614404688), `collector/p1_early_only_recovery.py` selects **exactly eight** distinct issuer codes from the 32 codes **present in the retrospectively queried 2025-05-26 vendor list but absent from the retrospectively queried 2026-10-20 list** (excluding the original 24 research issuers). This uses hindsight to select **stress-test research subjects, never backtest as-of candidates**.

Real public cloud [#39699471799](https://github.com/tiandi0228/ashare-free-data/actions/runs/39699471799) **SUCCESS**, **160 offline tests**, a single source login + **8 logical free-provider bar queries**, **2,444** original vendor rows (**2,225** vendor `tradestatus=1`, **219** `tradestatus=0`). Selected codes: `sh.600190`, `sh.600193`, `sh.600200`, `sh.600355`, `sh.600387`, `sh.600462`, `sh.600599`, `sh.600608`. Each was returned with its own byte SHA-256, first/last vendor rows, last `tradestatus=1`. The capture only published **SHA/count/date quality metadata**, not vendor bar CSV; original 8 CSVs therefore have NOT undergone independent byte replay or permanent archival. This extends the purposive historical research sample from 24 to **32 non-overlapping issuers, 14,007 vendor rows obtained**, NOT a point-in-time verified full-market data backfill.

For **two** new sample issuers, directly referenced public Shanghai Stock Exchange announcements additionally distinguish last trade session from formal delisting effective date: `600190` notice published 2025-07-18 states final cleanup-trading session 2025-07-18 and **delisting 2025-07-25** ([SSE issuer notice](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20250718_10785880.shtml)); `600608` notice published 2026-06-29 states final cleanup-trading session 2026-06-29 and **delisting 2026-07-03** ([SSE issuer notice](https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260629_10823833.shtml)). These are official-host **webpage references reviewed in a web source**, NOT verified raw HTML plus SHA fetched on public GitHub Runner. We cannot generalize the two dates or official attribution across all eight without evidence. Permanent [metadata-only source report](reports/p1_early_only_8_historical_research_20261022.json); derived temporary Artifact `12392616020` expires 2026-11-05.

**Safety:** The network workflow was restored to **manual-only** after one successful capped run. Do not interpret retrospective vendor membership delta as an IPO/delisting or historical point-in-time trading universe. Raw vendor redistribution rights and durable source bytes remain unverified, historical ST/halts/delistings not complete, no market-wide historical bars or P4 OOS, `trade_gate=BLOCKED`, `orders=[]`, zero paid APIs. No private `tiandi0228/scripts` changes or private Actions usage.

## Next formal acceptance gates

1. Establish reliable no-cost and properly permitted historical dated
   universe snapshots with authoritative listing, suspensions, ST and
   delistings, including securities absent from today's pool.
2. Expand **bounded, resumable** history capture with authentic
   publisher/source timestamps and durable authorized storage. Verify
   checksum and individual code/day coverage, not only row counts.
3. Validate P4 historical point-in-time walk-forward, fees, slippage,
   realistic T+1/tradeable exits, genuinely out-of-sample net returns
   and forward shadow runs before any executable candidates.
4. Keep the private main strategy/recommendation workflow isolated and
   PR gates blocked until all evidence is independently audited.

See [Issue #1](https://github.com/tiandi0228/ashare-free-data/issues/1)
for the running quality and capability evidence log.
