import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from collector.p4_prospective_daily_capture import CODES, FIELDS, capture, verify_receipt


def utc(raw):
    return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)


FIRST = utc("2026-12-01T11:30:00")


class Provider:
    def __init__(self, mode="normal"):
        self.mode = mode
        self.calls = []
        self.error_code = "0"
        self.fields = FIELDS
        self.logged_out = False

    def login(self):
        return self

    def logout(self):
        self.logged_out = True

    def query_history_k_data_plus(self, code, **kwargs):
        self.calls.append((code, kwargs))
        day = kwargs["start_date"]
        assert kwargs["end_date"] == day and kwargs["adjustflag"] == "3"
        self.row = [day, code, "10", "10", "10", "10", "100", "1000", "3", "1"]
        if self.mode == "wrong_date":
            self.row[0] = "2026-12-02"
        if self.mode == "suspended":
            self.row[2:8] = [""] * 6
            self.row[-1] = "0"
        self.remaining = (0 if self.mode == "missing" or
                          (self.mode == "partial" and code == CODES[-1]) else
                          2 if self.mode == "duplicate" else 1)
        return self

    def next(self):
        self.remaining -= 1
        return self.remaining >= 0

    def get_row_data(self):
        return self.row


class DailyCaptureTests(unittest.TestCase):
    def test_no_provider_access_outside_window_or_before_evening(self):
        provider = Mock()
        with tempfile.TemporaryDirectory() as folder:
            for raw in ("2026-11-30T12:00:00", "2026-12-01T11:29:59",
                        "2026-12-05T12:00:00", "2027-02-01T12:00:00"):
                with self.subTest(raw=raw):
                    self.assertEqual(capture(folder, utc(raw), provider)["status"],
                                     "OUTSIDE_CAPTURE_WINDOW")
            self.assertFalse(list(Path(folder).iterdir()))
        provider.assert_not_called()

    def test_valid_rows_and_receipt_roundtrip_then_reject_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            client = Provider()
            result = capture(folder, FIRST, lambda: client)
            day = Path(folder) / "2026-12-01"
            self.assertEqual(result, verify_receipt(day))
            self.assertEqual(len(client.calls), 8)
            self.assertTrue(client.logged_out)
            self.assertEqual(result["trade_gate"], "BLOCKED")
            self.assertEqual(result["orders"], [])
            (day / result["rows"][0]["filename"]).write_text("altered")
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                verify_receipt(day)

    def test_duplicate_attempt_does_not_query_or_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            capture(folder, FIRST, Provider)
            provider = Mock()
            with self.assertRaises(FileExistsError):
                capture(folder, FIRST, provider)
            provider.assert_not_called()

    def test_wrong_day_and_duplicate_rows_never_publish_receipt(self):
        for mode in ("wrong_date", "duplicate"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                client = Provider(mode)
                with self.assertRaisesRegex(ValueError, "one matching daily row"):
                    capture(folder, FIRST, lambda: client)
                self.assertTrue(client.logged_out)
                self.assertFalse((Path(folder) / "2026-12-01/receipt.json").exists())

    def test_missing_partial_and_suspended_are_not_executable(self):
        for mode, count, status in (("missing", 0, "NO_VENDOR_ROWS_NOT_A_CALENDAR_PROOF"),
                                    ("partial", 7, "PARTIAL_VENDOR_ROWS"),
                                    ("suspended", 8, "PILOT_VENDOR_ROWS_ONLY")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                capture(folder, FIRST, lambda: Provider(mode))
                result = verify_receipt(Path(folder) / "2026-12-01")
                self.assertEqual(result["rows_observed"], count)
                self.assertEqual(result["status"], status)
                self.assertFalse(result["official_session_verified"])
                self.assertFalse(result["prospective_OOS_validated"])

    def test_midnight_rollover_never_publishes_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, "day boundary"):
                capture(folder, FIRST, Provider, clock=lambda: utc("2026-12-01T16:00:00"))
            self.assertFalse((Path(folder) / "2026-12-01/receipt.json").exists())
