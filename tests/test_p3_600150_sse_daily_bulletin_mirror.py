"""Synthetic safety regression for P3 dated exchange bulletin mirror acquisition."""
import unittest
from datetime import datetime, timezone
from collector.p3_600150_sse_daily_bulletin_mirror import (
    SOURCE_URL, MAX_BYTES, acquire, verify_pdf,
)


def fake_original():
    return b"%PDF-1.4\n" + b"Research fixture only" * 200 + b"\n%%EOF\n"


class SSEBulletinProbeTests(unittest.TestCase):
    def test_research_receipt_is_blocked(self):
        data, raw = acquire(fetch=lambda url: fake_original(),
                            now=datetime(2026, 11, 12, tzinfo=timezone.utc))
        self.assertEqual(data["trade_gate"], "BLOCKED")
        self.assertEqual(data["orders"], [])
        self.assertEqual(data["executable_candidates"], [])
        self.assertEqual(data["original_pdf_sha256"], verify_pdf(raw))
        self.assertFalse(data["official_exchange_origin_independently_authenticated"])
        self.assertFalse(data["official_daily_security_status_certified"])
        self.assertFalse(data["historical_PIT_verified"])

    def test_exact_requested_origin(self):
        seen = []
        def fetch(url):
            seen.append(url)
            return fake_original()
        acquire(fetch=fetch)
        self.assertEqual(seen, [SOURCE_URL])

    def test_bounded_pdf(self):
        self.assertLessEqual(len(fake_original()), MAX_BYTES)
        for bad in (b"", b"NOT PDF" * 1000, b"%PDF-" + b"x" * 4001,
                    b"%PDF-" + b"x" * (MAX_BYTES + 1)):
            with self.assertRaises(ValueError):
                verify_pdf(bad)

    def test_sha_integrity_detects_changed_bytes(self):
        good = fake_original()
        bad = good.replace(b"Research", b"Tampered")
        self.assertNotEqual(verify_pdf(good), verify_pdf(bad))

    def test_naive_capture_rejected(self):
        with self.assertRaises(ValueError):
            acquire(fetch=lambda url: fake_original(),
                    now=datetime(2025, 8, 18))

    def test_visual_claim_not_parser_verified(self):
        data, _ = acquire(fetch=lambda url: fake_original())
        row = data["visual_row_claim_unverified_by_byte_parser"]
        self.assertEqual(row["issuer"], "sh.600150")
        self.assertEqual(row["reported_halt_start"], "2025-08-13")
        self.assertIsNone(row["reported_halt_end"])
        self.assertEqual(data["outside_observed_day_trade_state"], "UNKNOWN")

    def test_research_capture_not_historical_first_publication(self):
        data, _ = acquire(fetch=lambda url: fake_original(),
                          now=datetime(2026, 11, 12, tzinfo=timezone.utc))
        self.assertTrue(data["capture_utc_not_first_publication"].startswith("2026-11-12"))
        self.assertFalse(data["historical_first_publication_instant_authenticated"])
