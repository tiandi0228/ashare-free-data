import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.baostock_dated_universe import csv_bytes
from collector.p1_roster_lock import (
    check_source, execute, materialize, pack, remote_create, unpack,
)


class PinnedRosterTests(unittest.TestCase):
    def source(self, day="2026-10-22"):
        codes = [
            [f"sh.{bucket * 1000 + i:06d}", "1", f"issuer{i}"]
            for bucket in (600, 601, 603)
            for i in range(1000)
        ]
        raw = csv_bytes(codes)
        quality = {
            "status": "OBSERVED_UNVERIFIED", "requested_day": day,
            "mainboard_prefix_rows": 3000,
            "mainboard_sha256": hashlib.sha256(raw).hexdigest(),
            "logical_queries": 1, "paid_api_calls": 0,
            "historical_PIT_verified": False, "publisher_authenticated": False,
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        }
        return raw, quality

    def test_pin_preserves_source_and_marks_reuse_stale(self):
        raw, quality = self.source()
        lock = pack(raw, quality, 212)
        self.assertEqual(unpack(lock)[0], raw)
        with tempfile.TemporaryDirectory() as root:
            report = materialize(lock, root, "EXISTING_PIN")
            self.assertEqual(report["source_sha256"], quality["mainboard_sha256"])
            self.assertEqual((Path(root)/"mainboard.csv").read_bytes(), raw)
            q = json.loads((Path(root)/"quality.json").read_text())
            self.assertEqual(q["requested_day"], "2026-10-22")
            self.assertTrue(q["snapshot_reused"])
            self.assertTrue(q["pinned_research_roster"])
            self.assertEqual(q["snapshot_origin_run"], 212)
            self.assertFalse(q["historical_PIT_verified"])
            self.assertEqual(q["trade_gate"], "BLOCKED")

    def test_existing_pin_wins_over_changed_vendor_csv(self):
        raw, quality = self.source()
        original = pack(raw, quality, 212)
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            new_raw, new_quality = self.source("2026-10-29")
            new_quality["mainboard_sha256"] = hashlib.sha256(new_raw).hexdigest()
            (path/"quality.json").write_text(json.dumps(new_quality))
            (path/"mainboard.csv").write_bytes(new_raw)
            with patch("collector.p1_roster_lock.remote_read", return_value=original):
                with patch("collector.p1_roster_lock.remote_create") as write:
                    report, pinned = execute("pin", "user/repo", root, run_id=220)
            self.assertTrue(pinned)
            self.assertEqual(report["selection"], "EXISTING_PIN")
            self.assertEqual((path/"mainboard.csv").read_bytes(), raw)
            self.assertEqual(json.loads((path/"quality.json").read_text())["requested_day"], "2026-10-22")
            write.assert_not_called()

    def test_first_valid_observation_is_saved_once(self):
        raw, quality = self.source()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path/"quality.json").write_text(json.dumps(quality))
            (path/"mainboard.csv").write_bytes(raw)
            with patch("collector.p1_roster_lock.remote_read", return_value=None):
                with patch("collector.p1_roster_lock.remote_create") as create:
                    report, pinned = execute("pin", "user/repo", root, run_id=220)
            self.assertTrue(pinned)
            self.assertEqual(report["selection"], "NEW_PIN")
            create.assert_called_once()
            self.assertEqual(create.call_args.args[1]["source_sha256"], quality["mainboard_sha256"])

    def test_missing_pin_read_does_not_invent_vendor_data(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("collector.p1_roster_lock.remote_read", return_value=None):
                report, locked = execute("read", "user/repo", root)
            self.assertFalse(locked)
            self.assertEqual(report["selection"], "NO_PIN_YET")
            self.assertFalse((Path(root)/"mainboard.csv").exists())

    def test_tampered_snapshot_or_unsafe_receipt_fails_closed(self):
        raw, quality = self.source()
        lock = pack(raw, quality, 212)
        lock["source_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            unpack(lock)
        unsafe = dict(quality, trade_gate="OPEN")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            check_source(raw, unsafe)
        wrong_size = dict(quality, mainboard_prefix_rows=2999)
        with self.assertRaisesRegex(ValueError, "size differs"):
            check_source(raw, wrong_size)

    def test_stale_fallback_requires_original_provenance(self):
        raw, quality = self.source()
        stale = dict(quality, status="FROZEN_VENDOR_SNAPSHOT_UNVERIFIED",
                     snapshot_reused=True, snapshot_origin_run=155)
        lock = pack(raw, stale, 212)
        with tempfile.TemporaryDirectory() as root:
            materialize(lock, root, "EXISTING_PIN")
            q = json.loads((Path(root)/"quality.json").read_text())
            self.assertEqual(q["snapshot_origin_run"], 155)
        stale["snapshot_origin_run"] = 0
        with self.assertRaisesRegex(ValueError, "origin"):
            pack(raw, stale, 212)

    def test_large_pin_upload_uses_stdin_not_argv(self):
        raw, quality = self.source()
        lock = pack(raw, quality, 212)
        with patch("collector.p1_roster_lock.github_api", return_value="{}") as api:
            remote_create("user/repo", lock)
        self.assertIn("--input", api.call_args.args)
        payload = json.loads(api.call_args.kwargs["input_data"])
        self.assertGreater(len(payload["content"]), 100000)
        self.assertEqual(payload["branch"], "main")


if __name__ == "__main__":
    unittest.main()
