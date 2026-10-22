"""Offline tests for manifest scope and batch safety."""
import json
from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

from collector.batch import capture, load_manifest
from tests.test_probe import FakeProvider

class BatchTests(unittest.TestCase):
    def test_success_with_frozen_manifest_and_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest=root/"manifest.txt"
            manifest.write_text("600000\n000001\n",encoding="utf-8")
            api=FakeProvider()
            self.assertEqual(capture(manifest,0,root/"out",api),0)
            report=json.loads((root/"out/quality.json").read_text())
            self.assertEqual(report["requested_count"],2)
            self.assertEqual(report["successful_issuer_count"],2)
            self.assertEqual(report["failed_issuer_count"],0)
            self.assertEqual(report["observed_issuer_coverage_fraction"],1.0)
            self.assertIsNotNone(datetime.fromisoformat(report["observed_at_utc"]).tzinfo)
            self.assertEqual(report["logical_sdk_calls"],2)
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertEqual(report["orders"],[])
            self.assertFalse(report["historical_point_in_time_universe_verified"])
            self.assertEqual(len(api.calls),2)
    def test_out_of_range_does_not_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"m.txt";p.write_text("600000\n")
            api=FakeProvider()
            with self.assertRaises(ValueError):
                capture(p,1,Path(tmp)/"out",api)
            self.assertEqual(api.calls,[])
    def test_duplicate_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"m.txt";p.write_text("600000\n600000\n")
            with self.assertRaises(ValueError):
                load_manifest(p)
    def test_invalid_listing_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"m.txt";p.write_text("300001\n")
            with self.assertRaises(ValueError):
                load_manifest(p)
    def test_partial_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=root/"m.txt";m.write_text("600000\n")
            self.assertEqual(capture(m,0,root/"out",FakeProvider(invalid=True)),2)
            report=json.loads((root/"out/quality.json").read_text())
            self.assertEqual(report["status"],"BLOCKED_PARTIAL")
            self.assertEqual(report["successful_issuer_count"],0)
            self.assertEqual(report["failed_issuer_count"],1)
            self.assertEqual(report["observed_issuer_coverage_fraction"],0.0)
            self.assertEqual(report["orders"],[])

if __name__=="__main__":
    unittest.main()
