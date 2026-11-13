# 600150 halt/resume evidence replay

Scope: 600150 only, 2025-08-13 through 2025-08-19. Research only. `trade_gate=BLOCKED`. This case does not certify PIT eligibility or establish when a live strategy first knew of resumption.

| Evidence | Source | SHA-256 verified on 2026-11-13 |
|---|---|---|
| 2025-059 halt notice | https://static.cninfo.com.cn/finalpage/2025-08-05/1224387134.PDF | `498e48ccc9651e9be9e32dd17eaf60e2e9b9ed43fc8be41b26c995308561a66e` |
| 2025-063 resume notice | https://static.cninfo.com.cn/finalpage/2025-08-19/1224504273.PDF | `a529af260766407070b8d800cb890b26d06bee07adca3192244fe225546a1dbe` |
| BaoStock original CSV | `research-csv-archive:5ba00fbd720fad90/shard_0013/sh_600150.csv` | `45bb1574dc7068d696d74bfb74491984a9c792444396f3be6f04abe295ed7c40` |

Download each notice to a scratch directory and verify its SHA-256 before extracting text with `pdftotext -layout`. Read the security-specific event table, not a date mentioned in the body for another notice. The halt table specifies August 13. The resumption table specifies August 18 as the end of the halt and August 19 as resumption. Each notice is issuer-authored and hosted on the disclosure platform.

Use the CSV alongside the matching `quality.json` from the same shard. Verify the CSV SHA-256 both against the value above and the receipt entry for `sh.600150`. Filter the `date` field and compare `tradestatus`. Reproduction observed:

| 2025 session | Vendor tradestatus |
|---|---|
| 08-13, 08-14, 08-15, 08-18 | 0 each |
| 08-19 | 1 |

The PDF disclosure paths and dates printed on the notices are not independent evidence of the precise first public availability timestamp. Vendor rows corroborate the observed daily state, but are not independent exchange state or calendar certification. Do not fill missing dates or infer intraday tradability. The remaining proof request is a publisher/exchange record binding the exact notice ID and first public availability time, plus independent exchange session/state evidence before certifying any interval.
