"""Exercise real handoff, sealing, and reconciliation contracts together."""
from datetime import datetime
import hashlib
import json
import unittest
from unittest.mock import patch

from collector.p4_daily_evidence import seal
from collector.p4_prospective_handoff import assess
from collector.p4_session_reconcile import reconcile


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
