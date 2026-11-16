# P2 evidence review through 2026-10-20

Archive commit: `968b47863467ebfd00154e38cdf50851f3c3285b`. Dates are Beijing calendar dates. Audit scope is three issuer/date explanations, not feature coverage, publication-time authentication, or historical PIT certification. Shard and CSV digests were verified by the gap replay.

| Issuer | Source shard | Original CSV SHA-256 | Corroborated explanation |
| --- | --- | --- | --- |
| sh.601091 | shard_0097 | a99a8383f8a3a41682a7264cac5a1a3097831bb2e456c2c36d09c188b8fcdf3d | IPO traded from 2026-09-17. Enumerating weekdays from listing through the cutoff minus the official closures gives 18 sessions. All 18 dates are present and vendor-marked tradable. The 21-row rule was not yet met. |
| sz.002717 | shard_0362 | ae1b73a1389f0629f64e130af4f2c1778f52ca837985e4b5f95ef14f048b81ac | Issuer notice dated 2026-10-17 records suspension from the 2026-10-13 open while under proposed delisting. The cutoff's vendor nontradability is consistent with that suspension. No delisting-effective date is inferred at cutoff. |
| sz.002731 | shard_0364 | 0486cfcd1af2ffd60a48911a3f94178e9bbe56daeca2c6232d83876688234510 | Issuer notices report suspension from 2026-09-01, continuation from 2026-09-07, and resumption into the delisting transition on 2026-10-23. The cutoff falls before resumption. |

## Primary sources and PDF fingerprints

- [SSE listing notice, 601091](https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20260916_10832340.shtml) and [issuer listing document](https://static.cninfo.com.cn/finalpage/2026-09-16/1225566496.PDF), SHA-256 `4773473e50aef9399dd2fdeb3bed28b698e33b28cb938658666fc892f6320b1b`.
- [SSE 2026 holiday notice](https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml). Exclude 2026-09-25 and 2026-10-01 through 2026-10-07 as well as weekends. Same-session list matched each CSV date, not just the count.
- [002717 issuer notice 2026-122](https://static.cninfo.com.cn/finalpage/2026-10-17/1225609701.PDF), SHA-256 `9c2f3777bf177f750d12ad4151884e8eaed4c87a26111ff93ea1fbc22c1b4376`.
- [002731 continued halt 2026-109](https://static.cninfo.com.cn/finalpage/2026-09-07/1225549792.PDF), SHA-256 `91fe7a9340a052348066bba2f413e0fe50bfbb757a71b99204980afb2faf4c77`.
- [002731 resumption 2026-113](https://static.cninfo.com.cn/finalpage/2026-10-16/1225607489.PDF), SHA-256 `8d2be086e1a9d3329a2c70739f04e57811d01671546cdc8e82fb86ac68cde1fd`.

No synthetic bars, no backfill across a halt, no ledger mutation. Three causes corroborated, zero feature gaps promoted. Historical PIT remains unverified and trade_gate=BLOCKED.
