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
