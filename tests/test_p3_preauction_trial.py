from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collector.p3_preauction_trial import run_trial
from collector.p3_preauction_receipt import SHANGHAI


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.t = datetime(2026, 11, 17, 9, 13, tzinfo=SHANGHAI)
        self.day = self.t.date()
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.out = Path(temp.name) / "trial"

    def wait(self, seconds):
        self.t += timedelta(seconds=seconds)

    def fetch(self, issuer):
        return dict(captured_at=self.t.isoformat(), source_time=self.t.isoformat(), raw_sha256="test",
                    timing=("SAME_DAY_CAPTURE_BEFORE_0915" if self.t.minute < 15 else
                            "NOT_CAPTURED_BEFORE_0915"))

    def run_probe(self, fetch):
        return run_trial(self.day, self.out, clock=lambda: self.t, wait=self.wait, fetch=fetch)

    def test_windows_control_and_no_overwrite(self):
        result = self.run_probe(self.fetch)
        self.assertEqual(result["same_day_preauction_observations"], 4)
        self.assertEqual(len(list(self.out.glob("*.json"))), 7)
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertFalse(result["preauction_visibility_certified"])
        self.t = self.t.replace(minute=13)
        with self.assertRaises(FileExistsError):
            self.run_probe(self.fetch)

    def test_source_failure_and_late_completion_are_not_counted(self):
        def fetch(issuer):
            if issuer == "sz.002249":
                raise TimeoutError()
            self.wait(35)
            return self.fetch(issuer)
        result = self.run_probe(fetch)
        self.assertEqual(result["same_day_preauction_observations"], 1)
        self.assertEqual([r["result"] for r in result["records"][:4]],
                         ["OUTSIDE_SLOT", "MISSED_SLOT", "CAPTURED", "SOURCE_ERROR"])

    def test_late_start_has_no_side_effect(self):
        self.t = self.t.replace(minute=15)
        with self.assertRaises(ValueError):
            self.run_probe(lambda _: self.fail("must not request"))
        self.assertFalse(self.out.exists())
