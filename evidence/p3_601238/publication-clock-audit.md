# 601238 publication clock audit (NO TRADES)

Scope: three A-share event notices already reconciled with the market archive in #357. The HKEX Title Search `Release Time` refers to that venue and document. Shanghai and Hong Kong civil times below are UTC+08:00, with minute precision. Use 09:15 (start of the SSE opening call auction), not 09:30, as the pre-opening evidence cutoff. A publication after the cutoff does not prove that all other channels were silent before it.

| A-share event | Official cross-venue evidence | Timing conclusion |
| --- | --- | --- |
| 2026-049, halt effective from 2026-09-14 opening | 2026-09-14 22:23, HKEX 2026091401307, issuer inside-information filing explicitly identifies SSE A shares and describes the already effective halt | After 09:15 on 2026-09-14. Does not establish the A-share halt announcement was visible before the opening auction. The 09:31 HKEX exchange notice applies to H shares only. |
| 2026-050, continuing halt | 2026-09-18 19:54, HKEX 2026091801432, overseas regulatory filing identifies A-share code 601238 and announcement 2026-050 | The progress disclosure was public on HKEX before the next trading day's 2026-09-21 09:15 cutoff. This does not identify the SSE first-release time. |
| 2026-053, resumption effective from 2026-09-29 opening | 2026-09-28 22:46, HKEX 2026092802059, separate issuer inside-information filing discloses the application to resume SSE A-share trading from 2026-09-29 | The resumption application and intended date were public before 2026-09-29 09:15. This filing is not the mainland risk-and-resumption original, nor proof that the SSE had confirmed the resumption at 22:46. |

Source pages:

- [HKEX Title Search for 02238](https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&market=SEHK&stockId=49316)
- [HKEX issuer inside information, A-share halt](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0914/2026091401307.pdf)
- [HKEX exchange notice for H-share halt](https://www.hkexnews.hk/listedco/listconews/sehk/2026/0914/2026091400163.htm)
- [HKEX overseas regulatory filing, 2026-050](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0918/2026091801432.pdf)
- [HKEX issuer inside information, A-share resumption application](https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0928/2026092802059.pdf)
- [SSE halt abstract, date label 2026-09-15](https://www.sse.com.cn/disclosure/listedinfo/summaries/indexDetail.shtml?SEQ=334692286)
- [Mainland resumption original, 2026-053](https://static.cninfo.com.cn/finalpage/2026-09-29/1225586271.PDF)
- [SSE trading rules, section 2.4.2](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml)

Do not fill the SSE first-release fields from HKEX timestamps, date-only labels, or CNINFO midnight index values. This establishes two scoped cross-venue pre-auction visibility observations, not three SSE first-release clocks or full historical point-in-time coverage. There is no change to the replay output, coverage ledger or issuer gap closure. Trade gate stays BLOCKED.
