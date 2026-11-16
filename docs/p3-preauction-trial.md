# P3 one-date pre-auction diagnostic trial

Run from the PR branch checkout on an awake machine with network access and an
automatically synchronized system clock. On a confirmed A-share session date,
start at 09:10–09:13 China time. The script checks the specified local date
and weekday, not the exchange holiday calendar. The output parent must exist
and the named directory must not already exist.

Example for a session on 2026-11-17:

```sh
python3 -m collector.p3_preauction_trial --date 2026-11-17 \
  --out "$HOME/p3-preauction-2026-11-17"
```

There are two pre-auction windows (09:13:30–09:14:00, 09:14:20–09:15:00)
and one post-boundary control (09:15:10–09:16:00), each with at most one
request per symbol (600825 and 002249). The summary records misses, errors,
responses that complete outside their window, and provider clock timing.
Exit 2 means no same-day in-window pre-auction observation. Inspect summary.json
and leave raw receipts on the private filesystem. No Actions artifacts, archive
ledger writes, or trade authority are involved.

These observations cannot establish source status mapping, exchange first
release, historical visibility, or P3 certification. A market-data timestamp
and host wall clock are retained separately. The host clock is not attested.
