import csv
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from collector.p2_independent_bars import FIELDS
from collector.p4_asof_chronological_replay import audit, observe_outcome, replay_issuer, signal_indices

EPOCH = "a" * 16
START = date(2026, 1, 1)


def day(index):
    return START + timedelta(days=index)


def sample_rows():
    return [
        {"date": day(i).isoformat(), "code": "sh.600000",
         "open": px, "high": px, "low": px, "close": px,
         "volume": "100", "amount": "1000", "adjustflag": "3", "tradestatus": "1"}
        for i, px in enumerate(["10"] * 21 + ["11"] * 8)
    ]


class ChronologicalReplayTests(unittest.TestCase):
    def test_future_prices_and_status_do_not_rewrite_signal(self):
        rows = sample_rows()
        prefix = list(signal_indices(rows[:22], day(19), day(21)))
        self.assertEqual(prefix, [21])
        rows[22]["tradestatus"] = "0"
        rows[23]["close"] = "99"
        self.assertEqual(list(signal_indices(rows, day(19), day(21))), prefix)
        clean = replay_issuer(sample_rows(), day(19), day(21), day(28))
        changed = replay_issuer(rows, day(19), day(21), day(28))
        self.assertEqual(clean[0]["signal_after_close"], changed[0]["signal_after_close"])
        self.assertEqual(clean[0]["forward_availability"]["5"], "VENDOR_ROWS_OBSERVED_NOT_FILL")
        self.assertEqual(changed[0]["forward_availability"]["5"], "VENDOR_SUSPENSION_OBSERVED")

    def test_future_ohlc_and_status_are_never_read_by_signal_engine(self):
        rows = sample_rows()
        rows[22:] = [{"date": row["date"]} for row in rows[22:]]
        self.assertEqual(list(signal_indices(rows, day(19), day(21))), [21])

    def test_validation_end_censors_and_ignores_later_status(self):
        rows = sample_rows()
        rows[27]["tradestatus"] = "0"
        self.assertEqual(observe_outcome(rows, 21, 5, day(26)), "RIGHT_CENSORED")
        self.assertEqual(observe_outcome(rows, 21, 4, day(26)), "VENDOR_ROWS_OBSERVED_NOT_FILL")
        self.assertEqual(observe_outcome(rows, 21, 5, day(27)), "VENDOR_SUSPENSION_OBSERVED")

    def test_crossing_in_gap_is_not_recounted_as_validation_signal(self):
        self.assertEqual(replay_issuer(sample_rows(), day(19), day(22), day(28)), [])
        self.assertEqual(list(signal_indices(sample_rows(), day(21), day(28))), [])

    def test_suspension_resets_crossing_state(self):
        rows = sample_rows()
        rows[20]["tradestatus"] = "0"
        self.assertEqual(list(signal_indices(rows, day(19), day(28))), [])

    def test_pinned_git_archive_and_csv_receipt(self):
        def run(root, *args):
            return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / EPOCH / "shard_0000"
            source.mkdir(parents=True)
            target = source / "sh_600000.csv"
            stream = io.StringIO()
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(sample_rows())
            raw = stream.getvalue().encode()
            target.write_bytes(raw)
            (source / "quality.json").write_text(json.dumps({
                "status": "OBSERVED_SUBSET_UNVERIFIED", "trade_gate": "BLOCKED", "orders": [],
                "historical_point_in_time_universe_verified": False, "issuer_count": 1,
                "results": [{"status": "OBSERVED_UNVERIFIED", "code": "sh.600000",
                             "sha256": hashlib.sha256(raw).hexdigest(), "rows": 29,
                             "tradable_rows": 29, "suspended_status_rows": 0}],
            }))
            run(root, "init", "-q")
            run(root, "add", ".")
            run(root, "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                "commit", "-qm", "source")
            commit = run(root, "rev-parse", "HEAD")
            args = (EPOCH, day(19).isoformat(), day(21).isoformat(), day(28).isoformat())
            result = audit(root, commit, *args)
            self.assertEqual(result["holdout_signal_count"], 1)
            self.assertEqual(result["trade_gate"], "BLOCKED")
            self.assertEqual(result["broker_fills_verified"], 0)
            self.assertFalse(result["historical_OOS_validated"])
            self.assertFalse(result["trade_returns_computed"])
            self.assertEqual(result["orders"], [])
            self.assertEqual(result["issuer_prefix_checks_passed"], 1)
            with self.assertRaisesRegex(ValueError, "pinned commit"):
                audit(root, "0" * 40, *args)
            target.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "unchanged checkout"):
                audit(root, commit, *args)
            run(root, "add", ".")
            run(root, "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                "commit", "-qm", "changed source without matching receipt")
            with self.assertRaisesRegex(ValueError, "raw CSV hash mismatch"):
                audit(root, run(root, "rev-parse", "HEAD"), *args)


if __name__ == "__main__":
    unittest.main()
