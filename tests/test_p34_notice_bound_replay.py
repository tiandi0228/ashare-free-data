from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collector.p34_notice_bound_replay import SH_FILE, SH_SHA, calendar, reconcile_halt, replay_exit


class NoticeBoundReplayTests(unittest.TestCase):
    def test_two_official_originals_give_matching_scoped_schedule(self):
        sh = calendar("SH", "2026-09-24")
        sz = calendar("SZ", "2026-09-24")
        self.assertEqual(sh["rows"], sz["rows"])
        self.assertEqual(sh["source_sha256"], SH_SHA)
        self.assertNotEqual(sh["source_sha256"], sz["source_sha256"])
        self.assertFalse(sh["full_historical_calendar_authenticated"])

    def test_asof_uses_each_source_publication_boundary(self):
        for market, published in (("SH", "2025-12-22"), ("SZ", "2026-09-17")):
            with self.subTest(market=market):
                self.assertEqual(set(calendar(market, published)["rows"].values()), {"UNKNOWN_AS_OF"})

    def test_halt_reconciliation_keeps_missing_and_conflicting_separate(self):
        report = reconcile_halt(market="SZ", as_of="2026-09-24", halt_start="2026-09-24",
                                resume_day="2026-09-29",
                                vendor_status={"2026-09-24": "0", "2026-09-25": "0", "2026-09-29": "0"})
        self.assertEqual([x["outcome"] for x in report["rows"]],
                         ["MATCH", "VENDOR_ROW_ON_SCHEDULED_CLOSURE", "SCHEDULED_CLOSURE",
                          "SCHEDULED_CLOSURE", "MISSING_VENDOR_ROW", "STATUS_CONFLICT"])
        self.assertFalse(report["issuer_halt_notice_authenticated"])

    def test_exit_uses_notice_and_position_risk(self):
        for market in ("SH", "SZ"):
            scenario = dict(synthetic_test_case=True, market=market, entry_actual_fill="10.00",
                            stop_exit_actual_fill="9.50", shares=400)
            with self.subTest(market=market):
                result = replay_exit(entry_day="2026-09-30", exit_day="2026-10-08",
                                     as_of="2026-09-30", scenario=scenario)
                self.assertEqual(result["elapsed_scheduled_sessions"], 1)
                self.assertEqual(result["blocking_reasons"], ["POSITION_NET_STOP_BUDGET_EXCEEDED"])
                self.assertEqual(result["trade_gate"], "BLOCKED")
                self.assertFalse(result["fill_certified"])

    def test_tampered_sse_original_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / SH_FILE
            path.parent.mkdir(parents=True)
            path.write_bytes(SH_FILE.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "byte hash mismatch"):
                calendar("SH", "2026-09-24", Path(tmp))
