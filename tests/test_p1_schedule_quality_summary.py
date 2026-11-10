import copy
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_schedule_quality_summary import summarize
from collector.p1_schedule_run_provenance import build
from tests.test_p1_schedule_run_provenance import EPOCH, HEAD, github_run, valid_progress, sample_ledger


def make_receipt(run_id, created, *, cron="10 3 * * 1-5"):
    run = github_run(created, id=run_id)
    return build(run, valid_progress(before=0),
                 cron=cron, run_id=run_id, attempt=1, sha=HEAD,
                 actual_requested_shards=2, ledger=sample_ledger())


class P1ScheduleQualityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def save(self, row, *, folder=None):
        epoch = folder or row["source_sha256"][:16]
        dest = self.root / epoch
        dest.mkdir(exist_ok=True)
        p = dest / f"run_{row['run_id']}_attempt_{row['run_attempt']}.json"
        p.write_text(json.dumps(row))
        return p

    def test_two_realistic_delays_count_and_no_false_missed_slots(self):
        self.save(make_receipt(1001, "2026-11-05T03:20:00Z"))
        self.save(make_receipt(1002, "2026-11-06T06:20:00Z",
                               cron="10 3 * * 1-5"))
        report = summarize(self.root, EPOCH)
        self.assertEqual(report["observed_receipts"], 2)
        self.assertEqual(report["locally_SHA_ledger_accepted_shards_across_observed_runs"], 4)
        self.assertEqual(report["creation_delay_over_45m_count"], 1)
        self.assertEqual(report["creation_delay_over_180m_count"], 1)
        self.assertAlmostEqual(report["max_creation_delay_minutes"], 190)
        self.assertFalse(report["missing_cron_slots_inferred"])
        self.assertFalse(report["final_GitHub_workflow_conclusions_verified"])
        self.assertEqual(report["orders"], [])
        self.assertEqual(report["trade_gate"], "BLOCKED")

    def test_legacy_receipt_has_lag_but_no_locally_SHA_proven_delta(self):
        r=make_receipt(1201,"2026-11-05T03:20:00Z")
        r["per_shard_digests_from_locally_validated_ledger"]=False
        r["new_archived_shard_evidence"]=None
        self.save(r)
        summary=summarize(self.root,EPOCH)
        self.assertEqual(summary["observed_receipts"],1)
        self.assertEqual(summary["locally_SHA_ledger_accepted_shards_across_observed_runs"],0)
        self.assertEqual(summary["legacy_receipt_runs_without_local_SHA_proofs"],1)
        self.assertEqual(summary["legacy_reported_but_not_locally_SHA_proven_shard_deltas"],2)
        self.assertFalse(summary["final_GitHub_workflow_conclusions_verified"])

    def test_inflight_receipt_not_promoted_to_final_success(self):
        self.save(make_receipt(2001, "2026-11-05T03:20:00Z"))
        r = summarize(self.root)
        self.assertEqual(r["observed_receipts"], 1)
        self.assertFalse(r["full_market_history_verified"])
        self.assertFalse(r["automatic_dispatch_authorized"])
        self.assertFalse(r["writer_cutover_authorized"])

    def test_reject_tampered_delay_and_forged_shard_delta(self):
        for key, value in [
            ("github_queue_creation_delay_minutes", 0),
            ("checkpoint_shards_after", 20),
            ("shards_durably_accepted_by_run", 3),
            ("trade_gate", "OPEN"),
            ("github_workflow_conclusion_authenticated", True),
            ("new_archived_shard_evidence", []),
        ]:
            with self.subTest(key=key):
                row = make_receipt(3001, "2026-11-05T03:20:00Z")
                row[key] = value
                path = self.save(row)
                with self.assertRaises(ValueError):
                    summarize(self.root)
                path.unlink()

    def test_epoch_filter_and_duplicate_nominal_slot(self):
        row = make_receipt(4001, "2026-11-05T03:20:00Z")
        self.save(row)
        self.assertEqual(summarize(self.root,"b"*64)["observed_receipts"],0)
        duplicate = make_receipt(4002, "2026-11-05T03:25:00Z")
        self.save(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate epoch"):
            summarize(self.root)

    def test_wrong_file_binding_and_symlink_blocked(self):
        row=make_receipt(5001,"2026-11-05T03:20:00Z")
        path=self.save(row)
        changed=copy.deepcopy(row)
        changed["run_id"]=5002
        path.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            summarize(self.root)
        path.unlink()
        path.symlink_to(self.root)
        with self.assertRaisesRegex(ValueError,"symlink"):
            summarize(self.root)

    def test_empty_directory_distinguishes_missing_data_from_zero_progress(self):
        report=summarize(self.root)
        self.assertEqual(report["observed_receipts"],0)
        self.assertIsNone(report["max_creation_delay_minutes"])
        self.assertEqual(report["status"],
                         "OBSERVED_RECEIPTS_ONLY_NOT_FULL_CRON_COVERAGE")
        self.assertFalse(report["missing_cron_slots_inferred"])


if __name__ == "__main__":
    unittest.main()
