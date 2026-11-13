# 002717: as-of suspension, not a certified delisting date

P2 coverage reported `VENDOR_MARKED_NOT_TRADABLE_AT_ASOF` for this newly observed gap in shard_0362. The 2026-10-20 cutoff is unchanged.

| Evidence | Verified finding |
|---|---|
| [Issuer notice 2026-119](https://static.cninfo.com.cn/finalpage/2026-10-13/1225602315.PDF) | Suspension from market open on 2026-10-13. PDF SHA-256 `32a79fe046d35bcab49e962608d53500ad2da2067f70222346641e9cf5b2ba59`. |
| [Issuer notice 2026-122](https://static.cninfo.com.cn/finalpage/2026-10-17/1225609701.PDF) | Describes receipt of a preliminary SZSE delisting notice on 2026-10-16. Not an effective delisting decision. PDF SHA-256 `9c2f3777bf177f750d12ad4151884e8eaed4c87a26111ff93ea1fbc22c1b4376`. |
| Archived BaoStock original | `research-csv-archive:5ba00fbd720fad90/shard_0362/sz_002717.csv`. SHA-256 `ae1b73a1389f0629f64e130af4f2c1778f52ca837985e4b5f95ef14f048b81ac` matched shard quality.json. Oct 12 status 1. Oct 13–16, 19 and 20 status 0, with blank volume and amount. |

Keep the P2 gap. Do not use the carried close on a suspension row as an executable bar. No exact first-publication time, final delisting effective date or historical PIT state is certified by this check.

## Unresolved timing evidence for the previous three SSE cases

The public SSE company notice pages reviewed for 603517 and 603838 expose day-level dates, not a first-publication clock. SSE's [2026-09-29 financing-eligibility adjustment](https://www.sse.com.cn/disclosure/magin/announcement/ssereport/c/c_20260929_10833673.shtml) independently corroborates the 600363 risk-warning effective day of 2026-09-30. It is not the issuer's notice or proof of its publication time. Retain all three exact timestamps as unverified. `trade_gate=BLOCKED`.
