"""Exercise real handoff, sealing, and reconciliation contracts together."""
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile
import hashlib
import json
import unittest
from unittest.mock import patch

from collector.p4_daily_evidence import seal
from collector.p4_disclosure_run_clock import HANDOFF_FILE, RECEIPT_FILE, read_bound_zip
from collector.p4_disclosure_run_clock import verify as verify_run_clock
from collector.p4_prospective_handoff import assess
from collector.p4_session_reconcile import attach_run_provenance, reconcile


class ReceiptIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime.fromisoformat("2026-12-01T15:47:00+08:00")
        self.pin = dict(window_starts_beijing="2026-12-01T00:00:00+08:00",
                        window_ends_beijing_inclusive="2027-01-31",
                        registration_sha256="a" * 64, registration_commit="b" * 40,
                        github_run_id=43789424999)
        for module in ("p4_daily_evidence", "p4_session_reconcile"):
            self.enterContext(patch(f"collector.{module}.verify", return_value=self.pin))

    def handoff(self, **index_changes):
        safe = dict(trade_gate="BLOCKED", orders=[], executable_candidates=[])
        index = dict(safe, query_day="2026-12-01", pagination_complete=True,
                     query_day_time_filter_verified=True, raw_wrong_day_timestamps=0,
                     raw_invalid_timestamps=0, sample_page_stability_rechecks=[{"status": "MATCH"}] * 3,
                     unique_raw_announcement_ids=1, reported_total=1)
        index.update(index_changes)
        candidate = dict(safe, source_pagination_complete=True, candidate_count=1)
        pdf = dict(safe, candidates_available=1, attempted=1, successful=1, text_extracted_count=1,
                   text_extraction_failed_count=0)
        return (json.dumps(assess(index, candidate, pdf), ensure_ascii=False) + "\n").encode()

    def test_real_handoff_format_seals_and_replays_exact_bytes(self):
        raw = self.handoff()
        record = seal({}, {}, b"", raw, self.at)
        report = reconcile({}, {}, b"", [(record, raw)], self.at)
        self.assertEqual(record["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(report["rows"][0]["status"], "RETAINED")
        self.assertEqual(report["trade_gate"], "BLOCKED")
        self.assertFalse(report["prospective_OOS_validated"])
        with self.assertRaises(ValueError):
            reconcile({}, {}, b"", [(record, raw + b" ")], self.at)

    def test_failed_real_handoff_cannot_seal(self):
        with self.assertRaisesRegex(ValueError, "successful research-only"):
            seal({}, {}, b"", self.handoff(raw_wrong_day_timestamps=1), self.at)


    def actions_fixture(self, record, source):
        # Real ZIP bytes and exact handoff, with simulated Actions run metadata.
        out = BytesIO()
        with ZipFile(out, "w") as bundle:
            bundle.writestr(RECEIPT_FILE, json.dumps(record))
            bundle.writestr(HANDOFF_FILE, source)
        raw_zip = out.getvalue()
        repo, head = "fixture/repo", "c" * 40
        identity = dict(id=42, head_sha=head, head_branch="main")
        run = dict(identity, run_attempt=2, repository={"full_name": repo},
                   path=".github/workflows/p3-prospective-official-observation.yml",
                   status="completed", conclusion="success",
                   run_started_at="2026-12-01T07:35:00Z", updated_at="2026-12-01T07:50:00Z")
        artifact = dict(id=99, name="p4-registered-disclosure-42-2", expired=False,
                        workflow_run=identity, created_at="2026-12-01T07:48:00Z",
                        size_in_bytes=len(raw_zip), digest="sha256:" + hashlib.sha256(raw_zip).hexdigest())
        return run, artifact, raw_zip

    def reconcile_artifact(self, run, artifact, raw_zip):
        record, source = read_bound_zip(artifact, raw_zip)
        checks = verify_run_clock(run, artifact, record, repo="fixture/repo",
                                  run_id=42, attempt=2, head_sha="c" * 40)
        checks.update(verified_zip_digest=artifact["digest"], session_date=record["session_date"],
                      source_sha256=hashlib.sha256(source).hexdigest())
        report = reconcile({}, {}, b"", [(record, source)], self.at)
        return attach_run_provenance(report, [checks])

    def test_verified_zip_reaches_only_the_correct_retained_session(self):
        source = self.handoff()
        record = seal({}, {}, b"", source, self.at)
        run, artifact, raw_zip = self.actions_fixture(record, source)
        result = self.reconcile_artifact(run, artifact, raw_zip)
        kept = [row for row in result["rows"] if row["status"] == "RETAINED"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["date"], record["session_date"])
        self.assertEqual(kept[0]["source_sha256"], record["source_sha256"])
        proof = kept[0]["actions_provenance"]
        self.assertEqual((proof["run_id"], proof["run_attempt"], proof["artifact_id"]), (42, 2, 99))
        self.assertEqual(proof["verified_zip_digest"], artifact["digest"])
        self.assertTrue(all(row["actions_provenance"] is None
                            for row in result["rows"] if row["status"] != "RETAINED"))
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertFalse(result["prospective_OOS_validated"])

    def test_rejects_byte_drift_wrong_attempt_and_repacked_handoff(self):
        source = self.handoff()
        record = seal({}, {}, b"", source, self.at)
        run, artifact, raw_zip = self.actions_fixture(record, source)
        with self.assertRaisesRegex(ValueError, "digest or size"):
            self.reconcile_artifact(run, artifact, raw_zip + b"x")
        with self.assertRaisesRegex(ValueError, "selected disclosure attempt"):
            self.reconcile_artifact(run, dict(artifact, name="p4-registered-disclosure-42-1"), raw_zip)
        # Even with valid ZIP metadata, changed handoff bytes cannot reuse the old receipt.
        with self.assertRaisesRegex(ValueError, "invalid, future"):
            self.reconcile_artifact(*self.actions_fixture(record, source + b" "))
