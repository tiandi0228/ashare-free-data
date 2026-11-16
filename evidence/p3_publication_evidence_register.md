# P3 seven-issuer publication evidence register (NO TRADES)

This read-only companion annotates the existing fixed-archive replay. It does not change the aggregate replay's inputs, the coverage ledger, or certification. Times are Beijing time. Pre-auction means strictly before 09:15 for the relevant session. For a progress update, use the next relevant session, not a new suspension start.

| Security | Pinned source | Originals | Matched issuer-days | Notices with scoped pre-auction evidence | Mainland first releases verified | Evidence and limits |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 600825 | [#349 source](https://github.com/tiandi0228/ashare-free-data/blob/c1b454e19117c59ed956d609e6a26a7ed5f95120/collector/p3_600825_evidence_join.py) | 4 | 15 | 1 | 0 | 2026-018: Sep 18 19:32 media report before Sep 21 auction. Three originals have no timed comparison in this rollup. |
| 002860 | [#350 source](https://github.com/tiandi0228/ashare-free-data/blob/69b856e2939c05cf849748b28ce912c8dd5b3a65/collector/p3_002860_original_replay.py) | 3 | 11 | 0 | 0 | All three originals are replayed. Timing evidence is not classified in this rollup. |
| 002813 | [#353 source](https://github.com/tiandi0228/ashare-free-data/blob/dec0cb10649350e056fcf40117124a554387c1f2/evidence/p3_002813/publication-clock-audit.md) | 3 | 6 | 3 | 0 | Three timed media observations. 2026-025 also has a numbered 01:00:23 republication. The HKEX parent filing concerns the transaction, not the resumption date. |
| 605303 | [#354 source](https://github.com/tiandi0228/ashare-free-data/blob/b49e146359eb2c9df6e1df00c0fbaf87d075cde3/evidence/p3_605303/publication-clock-audit.md) | 3 | 11 | 3 | 0 | Three timed media observations, with continuing halt compared to the next session. |
| 002870 | [#355 source](https://github.com/tiandi0228/ashare-free-data/blob/6292e4335b9c6f68e962137e27416300aa2c0c61/evidence/p3_002870/publication-clock-audit.md) | 3 | 11 | 3 | 0 | Three timed media observations. Actual resumption comes from the separate resume notice, not a conditional deadline. |
| 603400 | [#356 source](https://github.com/tiandi0228/ashare-free-data/blob/82d1e1163c2e8b9b2a6d642e406ad2f7f5636fb6/evidence/p3_603400/publication-clock-audit.md) | 3 | 11 | 3 | 0 | Three timed media observations. 2026-048 also has a numbered 02:17 republication before the 09:15 cutoff. |
| 601238 | [#357 source](https://github.com/tiandi0228/ashare-free-data/blob/6d6b85fc2437fdab61b27acaf96afcb9d4c9a711/evidence/p3_601238/publication-clock-audit.md) | 3 | 11 | 2 | 0 | HKEX: 2026-050 continuing halt and 2026-053 resumption application/intended date only. 2026-049 media at 09:18 is during the auction, not pre-auction. H-share notices do not establish A-share timing. |
| **Total** | | **22** | **76** | **15** | **0** | **0 issuer gaps closed** |

Count each notice once. The 15 are 13 media-backed notice slots and 2 HKEX-backed slots. The HKEX application evidence covers the intended resumption date, not exchange confirmation. One further notice has a timed 09:18 intrauction observation and six have no classified timing observation in this register. Lack of classified evidence does not establish lack of public disclosure.

For mainland first release, the remaining evidence is a source-owned actual public dissemination record tying venue, timestamp, and timezone to a notice ID or original URL. A matching timestamped capture can establish availability by capture time, not exact first release. Do not use index midnight, date-only labels, unrelated document timestamps, or effective dates as publication times.

Trade gate remains `BLOCKED`. No orders or executable candidates. No formal P3 or P4 promotion.
