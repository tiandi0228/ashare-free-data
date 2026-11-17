from datetime import datetime
import unittest
from unittest.mock import patch

from collector.p4_session_reconcile import attach_run_provenance, reconcile


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-12-07T16:00:00+08:00")
        self.reg = self.enterContext(patch("collector.p4_session_reconcile.verify", return_value={
            "window_starts_beijing": "2026-12-01T00:00:00+08:00",
            "window_ends_beijing_inclusive": "2027-01-31",
        }))
        self.one = dict(session_date="2026-12-01", observed_at="2026-12-01T16:00:00+08:00",
                        source_sha256="a" * 64)
        self.seal = self.enterContext(patch("collector.p4_session_reconcile.seal", return_value=self.one))

    def run_check(self, pairs=()):
        return reconcile({}, {}, b"manifest", pairs, self.now)

    def test_distinguishes_supported_states(self):
        report = self.run_check([(self.one, b"source")])
        rows = {r["date"]: r["status"] for r in report["rows"]}
        self.assertEqual(len(rows), 62)
        self.assertEqual([rows[d] for d in ("2026-12-01", "2026-12-02", "2026-12-05",
                                            "2026-12-07", "2027-01-01")],
                         ["RETAINED", "NOT_IN_SUBMITTED_RUNS", "WEEKEND_CLOSED", "AWAITING_RECEIPT",
                          "CALENDAR_UNVERIFIED"])

    def test_rejects_changed_or_duplicate_receipts(self):
        with self.assertRaises(ValueError):
            self.run_check([(dict(self.one, source_sha256="b"), b"source")])
        with self.assertRaises(ValueError):
            self.run_check([(self.one, b"source")] * 2)

    def test_close_cutover_uses_beijing_time(self):
        for timestamp, status in (("2026-12-07T06:59:59+00:00", "PENDING_SESSION_CLOSE"),
                                  ("2026-12-07T07:00:00+00:00", "AWAITING_RECEIPT")):
            with self.subTest(timestamp=timestamp):
                self.now = datetime.fromisoformat(timestamp)
                report = self.run_check()
                rows = {r["date"]: r["status"] for r in report["rows"]}
                self.assertEqual(rows["2026-12-07"], status)
                self.assertEqual(rows["2026-12-08"], "PENDING_SESSION_CLOSE")
                self.assertEqual(rows["2026-12-04"], "NOT_CHECKED")
                self.assertEqual(report["coverage_scope"], "CALENDAR_ONLY")

    def test_before_window_preserves_bounded_notice_scope(self):
        self.now = datetime.fromisoformat("2026-11-16T12:00:00+08:00")
        report = self.run_check()
        rows = {r["date"]: r["status"] for r in report["rows"]}
        self.assertEqual(rows["2026-12-31"], "PENDING_SESSION_CLOSE")
        self.assertEqual(rows["2027-01-01"], "CALENDAR_UNVERIFIED")
        self.assertEqual(rows["2027-01-02"], "WEEKEND_CLOSED")
        self.assertEqual(set(report["calendar_notices"]), {"SSE", "SZSE"})
        self.assertFalse(report["official_calendar_fully_verified"])
        self.assertFalse(report["prospective_OOS_validated"])
        self.assertEqual(report["trade_gate"], "BLOCKED")

    def test_refuses_receipt_outside_notice_scope(self):
        self.now = datetime.fromisoformat("2027-01-04T17:00:00+08:00")
        record = dict(self.one, session_date="2027-01-04", observed_at="2027-01-04T16:00:00+08:00")
        self.seal.return_value = record
        with self.assertRaisesRegex(ValueError, "unverified-calendar"):
            self.run_check([(record, b"source")])


class RunProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.first = dict(session_date="2026-12-01", run_id=8, run_attempt=2,
                          artifact_id=90, source_sha256="a" * 64)
        self.second = dict(session_date="2026-12-02", run_id=9, run_attempt=1,
                           artifact_id=91, source_sha256="b" * 64)
        self.report = dict(rows=[
            dict(date=entry["session_date"], status="RETAINED", source_sha256=entry["source_sha256"])
            for entry in (self.first, self.second)
        ] + [dict(date="2026-12-03", status="NOT_IN_SUBMITTED_RUNS", source_sha256=None)])

    def test_binds_by_date_regardless_of_submission_order(self):
        result = attach_run_provenance(self.report, [self.second, self.first])
        self.assertEqual([row["actions_provenance"] for row in result["rows"]],
                         [self.first, self.second, None])
        self.assertNotIn("actions_provenance", self.report["rows"][0])

    def test_refuses_ambiguous_wrong_or_incomplete_provenance(self):
        for checks in ([self.first], [self.first, self.first],
                       [self.first, dict(self.second, source_sha256="c" * 64)],
                       [self.first, dict(self.second, artifact_id=90)],
                       [self.first, dict(self.second, run_id=8)],
                       [self.first, dict(self.second, session_date="2026-12-03")]):
            with self.subTest(checks=checks), self.assertRaisesRegex(ValueError, "provenance"):
                attach_run_provenance(self.report, checks)
