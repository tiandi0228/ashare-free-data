# 002870 pre-auction visibility audit (NO TRADES)

Times are Beijing time (UTC+08:00). Evaluate against 09:15, the start of the opening call auction under the [SZSE trading rules](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf). Media page times demonstrate contemporaneous public reporting of the facts, not public posting of the exact issuer PDF on an official venue.

| Pinned issuer notice | Timed public observation | Applicable comparison |
| --- | --- | --- |
| 2026-068 / 1225538772, [initial halt](https://static.cninfo.com.cn/finalpage/2026-09-01/1225538772.PDF) | [NBD, August 31 19:46:33](https://www.nbd.com.cn/articles/2026-08-31/4567748.html), reports the September 1 halt for the proposed acquisition. | Before September 1 09:15. The initial notice's conditional September 15 deadline is not proof of actual resumption. |
| 2026-069 / 1225550443, [progress](https://static.cninfo.com.cn/finalpage/2026-09-08/1225550443.PDF) | [Sina 7x24, September 7 15:45](https://finance.sina.com.cn/7x24/2026-09-07/doc-iniqyvru9567720.shtml), reports the ongoing negotiations and continued halt, matching the progress notice's substance. | Before September 8 09:15. This is a status update during an existing halt, not proof of a new suspension or of publication before the September 7 auction. |
| 2026-073 / 1225563563, [separate resumption notice](https://static.cninfo.com.cn/finalpage/2026-09-15/1225563563.PDF) | [JRJ/Gelonghui, September 14 19:38:58](https://finance.jrj.com.cn/2026/09/14193858428932.shtml), reports resumption from September 15 opening. | Before September 15 09:15. The actual resumption clause comes from the separate notice. |

The three CNINFO midnight index values are not used as first-release timestamps. No official first-release clock was verified. The eleven daily status records are unchanged (ten suspended, one resumed). Three scoped public-reporting observations, zero formally closed issuer gaps, no ledger write, and trade gate BLOCKED.

## Mainland first-release cross-check

| Notice / CNINFO ID | Index value (Unix ms) | UTC | Beijing time |
| --- | ---: | --- | --- |
| 2026-068 / 1225538772 | 1788192000000 | 2026-08-31 16:00 | 2026-09-01 00:00 |
| 2026-069 / 1225550443 | 1788796800000 | 2026-09-07 16:00 | 2026-09-08 00:00 |
| 2026-073 / 1225563563 | 1789401600000 | 2026-09-14 16:00 | 2026-09-15 00:00 |

The [pinned raw index](index.json) returns midnight Beijing date labels for all three notices. The timed reports above are earlier than the respective labels. In particular the continuing-halt item was reported September 7 at 15:45 Beijing time, so even reading the preceding calendar day's 16:00 UTC rendering as 16:00 Beijing would not be a defensible first-public clock. The issuer progress notice carries a September 7 board date and the later issuer history cites September 8 as the disclosure date; neither supplies an actual first-public clock.

The publicly indexed [SZSE halt/resumption listing](https://www.szse.cn/disclosure/notice/temp/index.html) and the inspected [HKEX Joyson 00699 title results](https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&market=SEHK&stockId=1000279756) did not yield a matching timed publication tying any of the three notice IDs to its original. The public archive lookup for the resumption PDF did not yield a usable response; archive coverage is unknown. To close the official-first-release gap, retain an exchange or designated platform dissemination log/receipt binding the notice ID or original URL to actual public release and time zone. A byte-matched, time-stamped capture can establish availability by capture time only. No ledger, replay or gate changes.
