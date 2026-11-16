import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from collector.p3_000582_asof_replay import DECISIONS, replay_clock
from collector.p3_000582_halt_replay import SOURCES
from collector.p3_000582_publication_clock import INDEX


class DecisionReplayTests(unittest.TestCase):
    def setUp(self):
        self.clock = dict(phase="P3_000582_PUBLICATION_CLOCK_AUDIT", trade_gate="BLOCKED",
                          historical_PIT_verified=False, historical_decision_time_eligibility_verified=False,
                          index_value_is_not_first_publication_time=True, orders=[], executable_candidates=[],
                          notices={key: dict(original_sha256=SOURCES[key][1], announcement_id=aid,
                                             index_date_beijing=day, first_publication_time_verified=False)
                                   for key, (aid, day) in INDEX.items()})
        raw = b"date,code\n2026-10-08,sz.000582\n2026-10-12,sz.000582\n"
        self.bars = Path(self.enterContext(TemporaryDirectory())) / "bars.csv"
        self.bars.write_bytes(raw)
        self.enterContext(patch("collector.p3_000582_asof_replay.VENDOR_SHA", hashlib.sha256(raw).hexdigest()))

    def test_dates_and_even_exact_clock_text_do_not_unlock(self):
        self.clock["notices"]["resume"]["index_value_beijing_not_publication_proof"] = "2026-10-11T08:00:00+08:00"
        report = replay_clock(self.clock, self.bars)
        self.assertEqual([case["decision_beijing"] for case in report["cases"]], list(DECISIONS))
        for case in report["cases"]:
            self.assertEqual(case["asof"]["publication_proof_status_counts"],
                             {"FIRST_PUBLICATION_NOT_AUTHENTICATED": 2})
            self.assertEqual(len(case["proof_queue"]["tasks"]), 2)
            self.assertEqual(case["bar_audit"]["certified_issuer_day_state_rows"], 0)

    def test_refuses_claimed_first_publication_or_other_bars(self):
        self.clock["notices"]["resume"]["first_publication_time_verified"] = True
        with self.assertRaisesRegex(ValueError, "unsupported publication"):
            replay_clock(self.clock, self.bars)
        self.clock["notices"]["resume"]["first_publication_time_verified"] = False
        self.bars.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "pinned vendor bars"):
            replay_clock(self.clock, self.bars)
