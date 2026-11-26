import base64
import hashlib
import unittest

from collector.p3_preauction_receipt import receipt


class PreauctionReceiptTests(unittest.TestCase):
    def make(self, **override):
        return receipt(**(dict(raw=b'{"code":"600825","state":"P"}', issuer="sh.600825",
                               source_url="https://example.test/status",
                               source_time="2026-09-07T01:14:00Z",
                               captured_at="2026-09-07T09:14:59+08:00",
                               status="HALTED", mapping="fixture/v1 state=P") | override))

    def test_preserves_bytes_without_certifying_user_supplied_clocks(self):
        result = self.make()
        self.assertEqual(result["timing"], "SAME_DAY_CAPTURE_BEFORE_0915")
        raw = base64.b64decode(result["raw_base64"])
        self.assertEqual(raw, b'{"code":"600825","state":"P"}')
        self.assertEqual(result["raw_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual((result["trade_gate"], result["orders"]), ("BLOCKED", []))
        self.assertFalse(result["preauction_visibility_certified"])
        self.assertFalse(result["capture_clock_attested"])
        self.assertIsNone(result["official_first_release"])

    def test_later_capture_cannot_backdate(self):
        for stamp in ("2026-09-07T09:15:00+08:00", "2026-09-07T16:00:00+08:00"):
            self.assertEqual(self.make(captured_at=stamp)["timing"], "NOT_CAPTURED_BEFORE_0915")

    def test_stale_and_missing_clock_are_distinct(self):
        self.assertEqual(self.make(source_time="2026-09-06T09:00:00+08:00")["timing"],
                         "SOURCE_NOT_CAPTURE_DAY")
        self.assertEqual(self.make(source_time=None)["timing"], "NO_SOURCE_CLOCK")

    def test_rejects_future_source_and_naive_capture(self):
        for kwargs in (dict(source_time="2026-09-07T09:15:00+08:00"),
                       dict(captured_at="2026-09-07T09:14:59")):
            with self.assertRaises(ValueError):
                self.make(**kwargs)

    def test_rejects_invalid_status_or_sensitive_url(self):
        for kwargs in (dict(status="GUESSED_FROM_ZERO_VOLUME"),
                       dict(source_url="https://user@example.test/x"),
                       dict(source_url="https://example.test/x?token=secret"),
                       dict(raw=b"")):
            with self.assertRaises(ValueError):
                self.make(**kwargs)
