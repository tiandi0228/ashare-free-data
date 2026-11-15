# 002813 pre-auction visibility audit (NO TRADES)

Scope: public visibility of the halt, extension and resumption facts already reconciled with the six archived A-share daily states in #353. An independently timestamped public media item supplies a latest-known observation of the fact, not the exact time the issuer's PDF first became public on SZSE or CNINFO. All times are Beijing time (UTC+08:00). Compare to 09:15, the start of the SZSE opening call auction under rule 2.4.2.

| Event / pinned original | Supporting contemporaneous report | Event-day auction cutoff | Margin to cutoff |
| --- | --- | --- | --- |
| 2026-022, initial halt from September 30 opening ([CNINFO original](https://static.cninfo.com.cn/finalpage/2026-09-30/1225589222.PDF)) | [CLS, September 29 20:37:46](https://api3.cls.cn/share/article/2495526?app=&os=ios&sv=882), summarizes the issuer's companion abnormal-movement announcement and its plan to halt from September 30. [NBD](https://www.nbd.com.cn/articles/2026-09-29/4595116.html) also reports the September 29 evening announcement and the same effective date. | 2026-09-30 09:15 | 12h 37m 14s |
| 2026-023, extension from October 9 opening ([CNINFO original](https://static.cninfo.com.cn/finalpage/2026-10-09/1225597548.PDF)) | [NBD, October 8 18:45:15](https://www.nbd.com.cn/articles/2026-10-08/4598862.html), reports continued suspension from October 9 opening for no more than three trading days. | 2026-10-09 09:15 | 14h 29m 45s |
| 2026-025, resumption from October 14 opening ([SZSE original](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-10-14/6b255775-6b1f-4f4a-aa78-37830de08dc2.PDF)) | [NBD, October 13 21:45:49](https://www.nbd.com.cn/articles/2026-10-13/4603546.html), reports the October 14 resumption date. The exchange PDF specifies opening as the effective time. | 2026-10-14 09:15 | 11h 29m 11s |

The [SZSE trading rules](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf) define the auction cutoff. The CNINFO index labels, announcement effective dates and media page timestamps remain separate fields. This audit adds three secondary-source bounds, zero verified official first-release clocks and zero closed issuer gaps. The replay schema and coverage ledger are unmodified. Trade gate remains BLOCKED.

## Official publication-clock cross-check

| Notice | CNINFO announcement ID | Raw `announcementTime` (Unix ms) | UTC rendering | Beijing rendering |
| --- | --- | ---: | --- | --- |
| 2026-022 | 1225589222 | 1790697600000 | September 29 16:00 | September 30 00:00 |
| 2026-023 | 1225597548 | 1791475200000 | October 8 16:00 | October 9 00:00 |
| 2026-025 | 1225604178 | 1791907200000 | October 13 16:00 | October 14 00:00 |

These conversions use the pinned [CNINFO index rows](index.json). The corresponding public reports precede all three Beijing date-label midnights. Rendering the raw fields in UTC produces the previous calendar day's 16:00, not evidence of a 16:00 Beijing release. The checked SZSE resumption original gives the effective time, not the first publication clock. The publicly accessible records checked did not establish the first publication time of the three PDFs. This is a scoped negative result, not a claim about what the exchanges retain internally.

[HKEX Title Search for Zoomlion (01157)](https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&lang=EN&market=SEHK&stockId=56944) gives October 13 21:35 (UTC+08:00) for the controlling shareholder's [disposal announcement](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/1013/2026101301047.pdf). The PDF identifies target 002813 and discloses the signed conditional transfer, but does not give the target's resumption date. Classify this timestamp as official cross-venue evidence of public availability of the transaction terms only. Do not treat it as publication of 2026-025 or proof of the resumption clause at 21:35.

No verified mainland first-release clock, gap closure, coverage ledger write or trade authorization results from this cross-check.
