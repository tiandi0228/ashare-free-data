# 603400 publication-clock audit (NO TRADES)

This note supplements the SHA-pinned originals and eleven vendor trading-day statuses in #356. All media and auction times are Beijing time (UTC+08:00). Under the [SSE trading rules](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml), 09:15 starts the opening call auction.

| Pinned issuer notice | Independent evidence | Audit classification |
| --- | --- | --- |
| [2026-047 / 1225564363](https://static.cninfo.com.cn/finalpage/2026-09-15/1225564363.PDF), halt from September 15 opening | [CLS, September 14 23:38](https://www.cls.cn/detail/2482825) reports the next-day halt. [Shanghai Securities News, September 15 08:36](https://www.cnstock.com/commonDetail/790223) confirms the opening halt clause. | Halt fact publicly reported before September 15 09:15. Neither page supplies the SSE first publication time. |
| [2026-048 / 1225573898](https://static.cninfo.com.cn/finalpage/2026-09-22/1225573898.PDF), continuing halt | [Gelonghui via Sina, September 21 16:05](https://finance.sina.com.cn/stock/bxjj/2026-09-21/doc-inisqriz7715529.shtml) reports the continued halt. [Sina's Shanghai Securities News republication, September 22 02:17](https://finance.sina.com.cn/roll/2026-09-22/doc-inisrnpt9099326.shtml), shows code 603400, notice number 2026-048 and the continued-halt clause. [China Securities Journal](https://epaper.cs.com.cn/zgzqb/html/2026-09/22/nw.D110000zgzqb_20260922_5-B023.htm) independently matches the numbered text but supplies an edition date only. | Progress fact publicly reported 17h 10m before September 22 09:15. Numbered text was republished 6h 58m before 09:15. This was an existing halt, and neither timestamp verifies the SSE/CNINFO PDF's first release. |
| [2026-051 / 1225588894](https://static.cninfo.com.cn/finalpage/2026-09-30/1225588894.PDF), resumption from September 30 opening | [NBD, September 29 22:38:29](https://www.nbd.com.cn/articles/2026-09-29/4595091.html) explicitly identifies the resumption announcement and next-day resumption. The pinned original specifies opening. | Resumption fact publicly reported before September 30 09:15. This does not timestamp the SSE original's first publication. |

| Notice / CNINFO ID | Raw index (Unix ms) | UTC rendering | Beijing rendering |
| --- | ---: | --- | --- |
| 2026-047 / 1225564363 | 1789401600000 | 2026-09-14 16:00 | 2026-09-15 00:00 |
| 2026-048 / 1225573898 | 1790006400000 | 2026-09-21 16:00 | 2026-09-22 00:00 |
| 2026-051 / 1225588894 | 1790697600000 | 2026-09-29 16:00 | 2026-09-30 00:00 |

The [raw CNINFO index](index.json) maps to Beijing midnight in all three cases. A previous-day 16:00 UTC rendering does not prove a 16:00 Beijing publication. No official first-release event was verified. Timed pre-auction reporting now covers all three event facts, with a separately timed numbered republication for 2026-048. Zero closed issuer gaps. No change to replay outputs or coverage ledger. Trade gate remains BLOCKED.
