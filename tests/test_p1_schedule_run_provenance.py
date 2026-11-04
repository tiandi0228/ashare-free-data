"""Scheduled source receipt must never confuse delayed cron with nearest slot."""
import base64
import copy
import datetime as dt
import json
import unittest
from unittest.mock import patch

from collector.p1_schedule_run_provenance import (
    ALLOWED_CRONS, DUAL_CRONS, build, nominal, path_for, persist,
)

UTC = dt.timezone.utc
EPOCH = "a"*64
HEAD = "b"*40


def valid_progress(*, selected=(60, 61), before=125):
    n = len(selected)
    return {
        "phase": "P1_READ_ONLY_RUN_PROGRESS",
        "status": "DURABLE_PROGRESS" if n else "SUCCESS_NO_NEW_SHARD",
        "source_sha256": EPOCH,
        "trade_gate": "BLOCKED",
        "historical_PIT_verified": False,
        "orders": [],
        "executable_candidates": [],
        "archive_csv_replay_enabled": True,
        "archive_gap_issuers": 0,
        "previous_shards": before,
        "current_shards": before+n,
        "new_shards_durably_accepted": n,
        "new_shard_count": n,
        "new_selected_shards": list(selected),
        "effective_shard_count": 2 if n == 2 else 1,
    }


def github_run(created, **overrides):
    run = {
        "id": 999,
        "run_attempt": 1,
        "head_sha": HEAD,
        "event": "schedule",
        "path": ".github/workflows/p1-fresh-vendor-roster.yml",
        "head_branch": "main",
        "status": "in_progress",
        "created_at": created,
    }
    run.update(overrides)
    return run


def check(cron, created, progress=None, **overrides):
    return build(github_run(created, **overrides),
                 valid_progress() if progress is None else progress,
                 cron=cron, run_id=999, attempt=1, sha=HEAD,
                 actual_requested_shards=2 if cron in DUAL_CRONS else 1)


def sample_ledger():
    done = [
        {"index": n, "issuer_count": 8,
         "manifest_sha256": f"{n:064x}",
         "receipt_sha256": f"{n+100:064x}"}
        for n in (60,61)
    ]
    return {
        "phase": "P1_ROSTER_SHARD_LEDGER",
        "source_sha256": EPOCH, "shard_count": 100,
        "completed": done, "completed_shards": 2,
        "completed_issuers": 16,
        "pending_shards": [i for i in range(100) if i not in (60,61)],
        "next_shard": 0, "failed_in_this_reconciliation": [],
        "full_market_bars_certified": False,
        "historical_PIT_verified": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [],
    }


class P1ExactScheduledProvenanceTests(unittest.TestCase):
    def test_local_ledger_shard_sha_pinned_to_source_receipt(self):
        r = build(github_run("2026-11-05T03:20:00Z"),
                  valid_progress(before=0),
                  cron="10 3 * * 1-5", run_id=999, attempt=1,
                  sha=HEAD, actual_requested_shards=2,
                  ledger=sample_ledger())
        self.assertTrue(r["per_shard_digests_from_locally_validated_ledger"])
        self.assertEqual([x["index"] for x in r["new_archived_shard_evidence"]],
                         [60, 61])
        self.assertEqual(r["new_archived_shard_evidence"][0]["manifest_sha256"],
                         f"{60:064x}")
        self.assertEqual(r["new_archived_shard_evidence"][1]["receipt_sha256"],
                         f"{161:064x}")
        self.assertEqual(r["orders"], [])
        self.assertEqual(r["trade_gate"], "BLOCKED")

    def test_unsafe_local_ledger_never_creates_sha_claim(self):
        for change in (
            {"source_sha256": "e"*64},
            {"completed_shards": 1},
            {"trade_gate": "OPEN"},
            {"historical_PIT_verified": True},
            {"completed": []},
        ):
            with self.subTest(change=change):
                ledger = sample_ledger()
                ledger.update(change)
                with self.assertRaises(ValueError):
                    build(github_run("2026-11-05T03:20:00Z"),
                          valid_progress(before=0),
                          cron="10 3 * * 1-5", run_id=999, attempt=1,
                          sha=HEAD, actual_requested_shards=2,
                          ledger=ledger)

    def test_missing_local_shard_sha_and_archive_does_not_upgrade(self):
        # Retained only to parse pre-upgrade (legacy) receipts; actual
        # scheduled workflow now requires --ledger on every source run.
        r = check("10 3 * * 1-5", "2026-11-05T03:20:00Z")
        self.assertFalse(r["per_shard_digests_from_locally_validated_ledger"])
        self.assertIsNone(r["new_archived_shard_evidence"])

    def test_six_dual_plus_eight_single_crons_exact(self):
        self.assertEqual(len(ALLOWED_CRONS), 14)
        self.assertEqual(len(DUAL_CRONS), 6)
        self.assertIn("10 3 * * 1-5", DUAL_CRONS)
        self.assertNotIn("10 3 * * 6,0", ALLOWED_CRONS)

    def test_1110_china_is_0310_utc_and_not_same_day_unobserved(self):
        # Nov 5 Thursday. The previous-day 11:10 slot is not silently assumed.
        r = check("10 3 * * 1-5", "2026-11-05T03:35:20Z")
        self.assertEqual(r["nominal_slot_beijing"],
                         "2026-11-05T11:10:00+08:00")
        self.assertEqual(r["requested_shards"], 2)
        self.assertAlmostEqual(r["github_queue_creation_delay_minutes"],
                               25.333, places=2)
        self.assertEqual(r["shards_durably_accepted_by_run"], 2)
        self.assertFalse(r["github_workflow_conclusion_authenticated"])
        self.assertFalse(r["runner_step_start_authenticated"])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["trade_gate"], "BLOCKED")
        self.assertEqual(r["orders"], [])

    def test_three_hour_delay_cannot_be_attributed_to_1310_slot(self):
        # The actual cron is UTC 01:10, but GitHub queued it at 04:10.
        # Do not infer that the UTC 03:10 schedule ran from this timestamp.
        r = check("10 1 * * 1-5", "2026-11-05T04:10:00Z",
                  valid_progress(selected=(60,)))
        self.assertEqual(r["nominal_slot_beijing"],
                         "2026-11-05T09:10:00+08:00")
        self.assertEqual(r["github_queue_creation_delay_minutes"], 180)
        self.assertTrue(r["delay_exceeds_45_minutes"])
        self.assertEqual(r["requested_shards"], 1)

    def test_weekend_single_and_prior_utc_day_0110_beijing(self):
        weekend = check("10 1 * * 6,0", "2026-11-07T01:55:00Z",
                        valid_progress(selected=(60,)))
        self.assertEqual(weekend["requested_shards"], 1)
        self.assertEqual(weekend["nominal_slot_beijing"],
                         "2026-11-07T09:10:00+08:00")
        # Fri Nov 6 01:10 Beijing uses Thu Nov 5 UTC 17:10.
        early = check("10 17 * * 0-4", "2026-11-05T17:20:00Z",
                      valid_progress(selected=(60,)))
        self.assertEqual(early["nominal_slot_beijing"],
                         "2026-11-06T01:10:00+08:00")
        self.assertEqual(early["requested_shards"], 1)

    def test_wrong_weekday_unknown_cron_and_old_slot_fail_closed(self):
        for cron, creation in [
            ("10 3 * * 1-5", "2026-11-07T03:14:00Z"),
            ("10 3 * * 1-5", "2026-11-07T20:00:00Z"),
            ("10 3 * * 1-5", "2026-11-08T04:00:00Z"),
            ("10 2 * * 1-5", "2026-11-05T03:25:00Z"),
        ]:
            with self.subTest(cron=cron, creation=creation):
                with self.assertRaises(ValueError):
                    check(cron, creation)

    def test_forged_metadata_run_attempt_identity_and_branch_rejected(self):
        base = "2026-11-05T03:23:00Z"
        for bad in [
            {"event":"push"},
            {"path":".github/workflows/p1-public-intraday-snapshot.yml"},
            {"head_branch":"feature"},
            {"head_sha":"c"*40},
            {"run_attempt":2},
            {"id":1000},
            {"status":"cancelled"},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                check("10 3 * * 1-5", base, **bad)

    def test_invalid_archive_progress_and_trade_gate_rejected(self):
        original = valid_progress()
        for update in [
            {"trade_gate":"OPEN"},
            {"historical_PIT_verified":True},
            {"orders":[{"side":"BUY"}]},
            {"archive_gap_issuers":1},
            {"archive_csv_replay_enabled":False},
            {"new_shards_durably_accepted":3},
            {"current_shards":126},
            {"new_shard_count":1},
            {"new_selected_shards":[60,60]},
            {"source_sha256":"bad"},
        ]:
            with self.subTest(update=update):
                p=copy.deepcopy(original);p.update(update)
                with self.assertRaises(ValueError):
                    check("10 3 * * 1-5", "2026-11-05T03:15:00Z", p)

    def test_actual_request_must_match_literal_cron_policy(self):
        run=github_run("2026-11-05T03:25:00Z")
        for bad in (1, 0, 3, True, "2"):
            with self.subTest(actual=bad), self.assertRaises(ValueError):
                build(run, valid_progress(), cron="10 3 * * 1-5",
                      run_id=999, attempt=1, sha=HEAD,
                      actual_requested_shards=bad)

    def test_weekday_single_records_only_verified_own_shard(self):
        r=check("10 1 * * 1-5", "2026-11-05T01:15:00Z",
                valid_progress(selected=(60,)))
        self.assertEqual(r["new_original_shard_indices"], [60])
        self.assertEqual(r["checkpoint_shards_before"], 125)
        self.assertEqual(r["checkpoint_shards_after"], 126)

    def test_file_path_unique_and_create_only_with_readback(self):
        r=check("10 3 * * 1-5", "2026-11-05T03:12:00Z")
        path=path_for(r)
        self.assertIn("run_999_attempt_1.json", path)
        original=(json.dumps(r,sort_keys=True,ensure_ascii=False,
                             indent=2)+"\n").encode()
        with patch("collector.p1_schedule_run_provenance.gh",
                   side_effect=["{}",
                                json.dumps({
                                    "path":path,"sha":"blob",
                                    "content":base64.b64encode(original).decode(),
                                })]) as mock:
            self.assertEqual(persist("org/repo",r),path)
        self.assertEqual(mock.call_count,2)
        put=mock.call_args_list[0]
        self.assertEqual(put.args[0:2],("-X","PUT"))
        payload=json.loads(put.kwargs["input_data"])
        self.assertNotIn("sha",payload)
        self.assertEqual(payload["branch"],"main")
        self.assertEqual(base64.b64decode(payload["content"]),original)

    def test_remote_receipt_byte_mismatch_rejected(self):
        r=check("10 3 * * 1-5", "2026-11-05T03:12:00Z")
        bad=base64.b64encode(b"{}").decode()
        with patch("collector.p1_schedule_run_provenance.gh",
                   side_effect=["{}",json.dumps({
                       "path":path_for(r),"sha":"blob","content":bad
                   })]):
            with self.assertRaises(ValueError):
                persist("org/repo",r)


if __name__ == "__main__":
    unittest.main()
