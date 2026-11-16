from datetime import datetime
import unittest
from unittest.mock import patch

from collector.p4_session_reconcile import reconcile


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
                         ["RETAINED", "MISSING", "WEEKEND_CLOSED", "PENDING", "CALENDAR_UNVERIFIED"])

    def test_rejects_changed_or_duplicate_receipts(self):
        with self.assertRaises(ValueError):
            self.run_check([(dict(self.one, source_sha256="b"), b"source")])
        with self.assertRaises(ValueError):
            self.run_check([(self.one, b"source")] * 2)

    def test_no_missing_before_window(self):
        self.now = datetime.fromisoformat("2026-11-16T12:00:00+08:00")
        self.assertNotIn("MISSING", self.run_check()["counts"])
