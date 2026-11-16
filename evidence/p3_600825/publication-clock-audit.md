# 600825 pre-auction visibility audit (NO TRADES)

This note supplements the four SHA-pinned issuer originals and fifteen archived trading-day states in #349. All report times are Beijing time (UTC+08:00). The [SSE trading rules](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml) start the opening auction at 09:15.

| Original | Timed secondary evidence | Scope |
| --- | --- | --- |
| [2026-014 / 1225552231](https://static.cninfo.com.cn/finalpage/2026-09-08/1225552231.PDF) | [Yicai, September 7 19:16](https://www.yicai.com/brief/103354877.html) reports the September 8 opening continuation and recounts the September 7 halt. | Before September 8 09:15 for continued suspension only. It is after the September 7 session and does not establish pre-auction visibility of the initial halt. |
| [2026-018 / 1225571469](https://static.cninfo.com.cn/finalpage/2026-09-19/1225571469.PDF) | Existing [Securities Times observation](https://www.stcn.com/article/detail/4191231.html), September 18 19:32, from the pinned original replay. | Before September 21 09:15, unchanged from #349. |
| [2026-030 / 1225602155](https://static.cninfo.com.cn/finalpage/2026-10-13/1225602155.PDF) | [Eastmoney, October 12 19:14:48](https://gubapost.eastmoney.com/news,600825,1781474472.html) shows the numbered notice and October 13 opening halt clause. | Before October 13 09:15. This is the separate October risk-review halt, not the September asset-transaction halt. |
| [2026-031 / 1225607741](https://static.cninfo.com.cn/finalpage/2026-10-16/1225607741.PDF) | [Sina republication of Shanghai Securities News, October 16 01:45](https://finance.sina.com.cn/roll/2026-10-16/doc-inivivfx7939086.shtml) shows the issuer code, notice number and October 16 opening resumption clause. | Before October 16 09:15. The page time timestamps the republication, not the SSE original. |

Four notice slots now have at least one scoped observation. The September 7 initial halt is still unverified before 09:15, and all four mainland first-publication clocks are unverified. No issuer gap closure, no change to replay output, no coverage ledger update and no orders. Trade gate remains BLOCKED.

## September 7 first-halt follow-up

- The [historical Sohu schedule](https://q.stock.sohu.com/cn/600825/bw_38.shtml) confirms the whole-day halt but has no clock for when that status was originally published. The [September 7 morning JRJ roundup](https://finance.jrj.com.cn/2026/09/07073058369026.shtml) does not list 600825. Its omission is not proof that the exchange had not disclosed the halt before 09:15.
- [Jiemian via Sina, September 7 19:09](https://finance.sina.com.cn/jjxw/2026-09-07/doc-iniqyzxx0307698.shtml) reports both clauses. This is an earlier timed corroboration of the September 8 continuation, but retrospective for the September 7 halt. No September 7 pre-auction record was recovered.

### Evidence to obtain

| Evidence needed | Minimum fields to retain | What it would establish |
| --- | --- | --- |
| Public market-status snapshot or dissemination message for 600825 on September 7 | Security code, SSE venue and trading date, original source timestamp and time zone, status field and versioned field definition, original payload or archive checksum, delivery channel | Availability of explicit halt status by the snapshot/message time, only if earlier than 09:15 Beijing. A zero-volume bar, no returned ticks, or an effective-time field alone is insufficient. |
| Official public dissemination record for 2026-014 / 1225552231 | Notice identifier or exact PDF URL, venue, actual public release timestamp and time zone, provenance linking timestamp to event and document | Official publication timing. Submission, approval or operation confirmation without public release is not equivalent. |

[Shanghai Stock Exchange Information Network historical data](https://www.sseinfo.com/services/assortment/historical/) lists snapshots and auction data as potential sources. The public product description does not establish that this stock's pre-09:15 halt-status record is included. Confirm field semantics, coverage and access before depending on it. No source request, purchase, ledger update, certification or gate change was made.

### Exchange snapshot field preflight

The [production technical index](https://www.sse.com.cn/services/tradingtech/data/)
lists [IS120 Binary v0.62, July 3](https://www.sse.com.cn/services/tradingtech/data/c/10824278/files/0bd5b8920cef4b238b7bd398e734ce18.pdf)
before the event. The next production index entry for this protocol is dated
September 18. This is a dated reference for a proposed intake, not proof of the
schema of any vendor export. Sections 2.2.2, 2.5.1 and 2.5.3 describe an M102
stock snapshot (MD002) with product code, trading date, exchange SendingTime,
LastUpdateTime and eight-character TradingPhaseCode. Its first position P is an
explicit stock halt. Startup S, the nontradable flag by itself, or zero volume
does not qualify. The preflight uses the exchange send time and a strict
09:15:00 Beijing cutoff. It does not use the last update as a proxy for dispatch.

Before acquiring data, confirm whether historical Level-1/Level-2 samples
include SSE 600825 on 2026-09-07 strictly before 09:15:00 Beijing, whether a
halted instrument remains included, and whether the export preserves the
exchange send timestamp and explicit halt state with a dated field map.
Request the source/channel, coverage start, transformation notes, and original
file or provider checksum for independent review. A pre-auction exchange-feed
message can support only the evidenced dissemination scope, not the first
publication of the 2026-014 issuer notice.

The offline preflight accepts a normalized excerpt for structural screening
only. It is not a binary decoder, a provenance authenticator, or a claim that
any subscription or archive contains the record. No real excerpt is supplied
to CI. A missing row is not evidence of no halt or no disclosure.

### Historical export format confirmed

The [historical data interface 1.1.4](https://www.sseinfo.com/services/assortment/market/hqywwd/wdzsjk/c/10800481/files/43b75567ae224148bd576acf11d30bd3.pdf)
documents three export formats separately from the live Binary feed.

| Export | Explicit halt field | Time used to screen |
| --- | --- | --- |
| Level-1 Snapshot.csv, table 3-2 | PhaseCode starts with P | SendingTime (seconds), not DateTime |
| Level-2 Snapshot.csv, table 3-6 | TradingPhaseCode starts with P | SendingTime (seconds), not DateTime |
| Level-2 StockTick.csv, table 3-12 | Type S and TickBSFlag SUSP | SendingTime (seconds), not TickTime |

Request the September 7 StockTick product-state rows first, with the matching
snapshot as a cross-check. A schema listing does not establish that 600825 or
the pre-09:15 window exists in the actual export. No sample was acquired.
The CSV preflight is offline and does not authenticate extracted rows or
promote tested fixtures into evidence.

[IS124 v3.60](https://www.sse.com.cn/services/tradingtech/data/c/10831312/files/822eabc535c248c48f24d6f5e8143f27.pdf)
sections 2.8 and 2.9 document the two pre-market cpxx batches. They include
suspended products, so row presence does not distinguish halt status.
In the CPXX product-state flag, position four P is the main-board delisting
arrangement category, not a halt. The record update time is not a delivery
timestamp. Do not use CPXX as a shortcut for the historical status evidence.
