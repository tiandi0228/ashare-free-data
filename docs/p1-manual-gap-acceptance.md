# P1 bounded manual gap acceptance

This runbook is for research data only. It does not authorize trading or change the archive destination. The existing writer uses the `research-csv-archive` branch of the execution repository and the same-epoch checkpoint on `main`. Do not use this runbook to switch the writer to the private repository.

## Merge-triggered run

Merging PR #331 into `main` matches the existing path-filtered `push` trigger for the production collector. If that run starts, it uses the normal one-shard rotation with an empty `gap_window` and can write the existing research archive and checkpoint. It is not the targeted manual pilot and does not produce the manual acceptance receipt.

After an authorized merge, locate the push-triggered run by the merge commit SHA and let it finish before dispatching the pilot. Re-read the active roster, checkpoint and archive index after that run. If it already collected the intended shard, pick the first remaining gap from the fresh state. Also check for queued scheduled collection before dispatching the pilot.

## Before dispatch

1. Verify that the reviewed workflow is on the authorized execution ref, that the branch SHA matches the reviewed commit, and that CI passed. Do not launch the production writer from a draft branch.
2. Read the active original roster lock, the same-source checkpoint, and the same-source archive index. Confirm the completed index sets match and the chosen window still contains pending shards. Stop if the active source changed or the archive and checkpoint disagree. Do not dispatch while an ordinary P1 run is pending. GitHub's shared concurrency group serializes active jobs but does not preserve every queued job.
3. In **P1 fresh Baostock mainboard roster observation (NO TRADES)**, use `workflow_dispatch` on the reviewed production ref. For the first run, use `shards_per_run=1` and `gap_window=N:N` for the currently confirmed first pending shard. On the 257/400 snapshot the first candidate was `220:220`. Treat this as an example, not a fixed launch parameter. Leave `recovery_token` empty.

## Accept or stop

- Wait for the exact run and attempt to finish. The run artifact `p1-fresh-roster-<run_id>` must contain `p1_manual_gap_acceptance.json`. It must report `MANUAL_GAP_ARCHIVE_AND_CHECKPOINT_VERIFIED`, the expected workflow SHA, source SHA, run ID and attempt, audited archive commit, remote checkpoint blob SHA, and exactly the selected new shard in `accepted_shards`.
- Confirm that the shard's original receipt and CSV files exist at the audited archive commit. Independently re-read the live archive index and epoch checkpoint and compare the index sets. Compare the accepted shard entry, including its receipt SHA, to the live checkpoint. Later runs can add more shards, so use the per-run receipt to attribute the increment, not the difference between two global counters.
- A failed run or missing acceptance receipt is not a successful pilot. Inspect the preflight, archive audit, and checkpoint state before retrying. If Git accepted the archive but checkpoint verification failed, use the existing orphan reconciliation path. Do not force-push or overwrite the archived bytes.
- `trade_gate` stays `BLOCKED`. A successful pilot does not certify historical PIT coverage or unlock trading.
