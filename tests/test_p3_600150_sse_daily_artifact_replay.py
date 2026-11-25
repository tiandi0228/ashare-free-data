"""Synthetic tamper tests for exact-size frozen SSE-titled artifact replay."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from collector import p3_600150_sse_daily_artifact_replay as replay_mod
from collector.p3_600150_sse_daily_bulletin_mirror import SOURCE_URL, CLAIM


def synthetic():
    raw = b"%PDF-1.4\n" + b"x" * 35000 + b"\n%%EOF\n"
    digest = hashlib.sha256(raw).hexdigest()
    receipt = {
        "phase": "P3_600150_SSE_TITLED_DAILY_BULLETIN_MIRROR_RESEARCH",
        "source_url": SOURCE_URL, "mirrored_source_host": "dataclouds.cninfo.com.cn",
        "source_document_title_claim": "上海证券交易所2025年08月18日股票和可转债停复牌信息",
        "visual_row_claim_unverified_by_byte_parser": CLAIM,
        "original_pdf_sha256": digest, "original_pdf_bytes": len(raw),
        "capture_utc_not_first_publication": "2026-11-12T02:06:54+00:00",
        "pdf_raw_bytes_sha_replay_verified": True,
        "official_exchange_origin_independently_authenticated": False,
        "historical_first_publication_instant_authenticated": False,
        "official_daily_security_status_certified": False,
        "whole_halt_resume_interval_certified": False,
        "historical_PIT_verified": False,
        "outside_observed_day_trade_state": "UNKNOWN",
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
    return raw, digest, receipt


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "original.zip"
        self.raw, self.digest, self.receipt = synthetic()

    def write(self, *, raw=None, receipt=None, extra=False):
        with zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("receipt.json", json.dumps(self.receipt if receipt is None else receipt))
            archive.writestr(f"{self.digest}.pdf", self.raw if raw is None else raw)
            if extra: archive.writestr("unexpected.txt", "wrong")
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def run_verified(self, zip_sha):
        with (patch.object(replay_mod, "PDF_SHA256", self.digest),
              patch.object(replay_mod, "PDF_BYTES", len(self.raw))):
            return replay_mod.replay(self.path, pinned_zip_sha=zip_sha)

    def test_valid_fixture_stays_blocked(self):
        result = self.run_verified(self.write())
        self.assertEqual(result["pdf_bytes_verified"], len(self.raw))
        self.assertFalse(result["historical_PIT_verified"])
        self.assertFalse(result["visual_claim_parsed_and_certified"])
        self.assertEqual(result["orders"], [])

    def test_zip_tamper_refused(self):
        original = self.write()
        self.write(extra=True)
        with self.assertRaises(ValueError): self.run_verified(original)

    def test_pdf_tamper_refused(self):
        digest = self.write(raw=self.raw.replace(b"x", b"y", 1))
        with self.assertRaises(ValueError): self.run_verified(digest)

    def test_extra_entry_refused(self):
        with self.assertRaises(ValueError): self.run_verified(self.write(extra=True))

    def test_false_historical_certification_refused(self):
        self.receipt["official_daily_security_status_certified"] = True
        with self.assertRaises(ValueError): self.run_verified(self.write())

    def test_false_first_publication_refused(self):
        self.receipt["historical_first_publication_instant_authenticated"] = True
        with self.assertRaises(ValueError): self.run_verified(self.write())

    def test_wrong_capture_time_refused(self):
        self.receipt["capture_utc_not_first_publication"] = "2025-08-18T00:00:00+00:00"
        with self.assertRaises(ValueError): self.run_verified(self.write())

    def test_trades_never_unblocked(self):
        self.receipt["trade_gate"] = "OPEN"
        with self.assertRaises(ValueError): self.run_verified(self.write())
