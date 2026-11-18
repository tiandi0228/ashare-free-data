from datetime import datetime
import hashlib
import json
import unittest
from unittest.mock import patch

from collector.p4_daily_evidence import seal


class DailyEvidenceTests(unittest.TestCase):
    def setUp(self):
        pin = dict(window_starts_beijing="2026-12-01T00:00:00+08:00",
                   window_ends_beijing_inclusive="2027-01-31", registration_sha256="abc",
                   registration_commit="def", github_run_id=123)
        self.verify = self.enterContext(patch("collector.p4_daily_evidence.verify", return_value=pin))
        self.source = dict(phase="P3_TO_P4_PROSPECTIVE_HANDOFF", date="2026-12-01",
                           capture_checks_all_passed=True, trade_gate="BLOCKED", orders=[],
                           historical_backtest_input_eligible=False, executable_candidates=[])

    def sample(self, now="2026-12-01T07:05:00+00:00", **changes):
        raw = json.dumps(dict(self.source, **changes)).encode()
        return seal({}, {}, b"manifest", raw, datetime.fromisoformat(now)), raw

    def test_research_only_and_raw_digest(self):
        r, raw = self.sample()
        self.assertEqual(r["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(r["registration_sha256"], "abc")
        self.assertFalse(r["prospective_OOS_validated"])
        self.assertFalse(r["strategy_prices_verified"])

    def test_missing_or_unsafe_receipt_rejected(self):
        for changes in ({"orders": ["x"]}, {"capture_checks_all_passed": False},
                        {"historical_backtest_input_eligible": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.sample(**changes)

    def test_timing_fails_closed(self):
        for now, day in (("2026-12-01T14:59:59+08:00", "2026-12-01"),
                         ("2026-12-02T15:15:00+08:00", "2026-12-01"),
                         ("2026-11-30T15:15:00+08:00", "2026-11-30"),
                         ("2026-12-05T15:15:00+08:00", "2026-12-05")):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.sample(now, date=day)

    def test_requires_valid_pre_window_pin(self):
        self.verify.side_effect = ValueError("bad pin")
        with self.assertRaisesRegex(ValueError, "bad pin"):
            self.sample()
