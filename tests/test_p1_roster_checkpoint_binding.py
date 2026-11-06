"""Verify original roster CSV bytes before identifying a matching epoch."""
import copy
import hashlib
import unittest
from collector.baostock_dated_universe import csv_bytes
from collector.p1_roster_lock import pack
from collector.p1_roster_checkpoint_binding import bind
from tests.test_p1_epoch_status import ledger

A = "a" * 64
B = "b" * 64


def roster():
    rows = [
        [f"sh.{bucket * 1000 + i:06d}", "1", f"issuer{i}"]
        for bucket in (600, 601, 603)
        for i in range(1000)
    ]
    raw = csv_bytes(rows)
    sha = hashlib.sha256(raw).hexdigest()
    receipt = {
        "phase": "P1_FRESH_VENDOR_ROSTER",
        "status": "FROZEN_VENDOR_SNAPSHOT_UNVERIFIED",
        "requested_day": "2026-10-28",
        "snapshot_reused": True, "snapshot_origin_run": 99,
        "mainboard_prefix_rows": 3000, "mainboard_sha256": sha,
        "logical_queries": 1, "paid_api_calls": 0,
        "publisher_authenticated": False, "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
    lock = pack(raw, receipt, 100)
    return lock, sha


class BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.sha = roster()

    def test_matching_epoch_is_original_byte_verified_and_research_only(self):
        report = bind(self.original, {B: ledger(B, range(82)),
                                       self.sha: ledger(self.sha, range(163))})
        self.assertEqual(report["status"], "MATCHED_UNVERIFIED_RESEARCH_EPOCH")
        self.assertEqual(report["matched_epoch"], self.sha)
        self.assertEqual(report["completed_shards"], 163)
        self.assertEqual(report["checkpoint_percent"], 40.75)
        self.assertTrue(report["original_csv_bytes_reverified"])
        self.assertFalse(report["historical_PIT_verified"])
        self.assertFalse(report["full_market_bars_certified"])
        self.assertEqual(report["orders"], [])
        self.assertEqual(report["trade_gate"], "BLOCKED")

    def test_missing_epoch_never_falls_back_to_largest_count(self):
        report = bind(self.original, {B: ledger(B, range(200))})
        self.assertEqual(report["status"], "PINNED_EPOCH_CHECKPOINT_MISSING")
        self.assertIsNone(report["matched_epoch"])
        self.assertIsNone(report["checkpoint_percent"])
        self.assertTrue(report["original_csv_bytes_reverified"])

    def test_tampered_csv_fails_despite_matching_declared_hashes(self):
        changed = copy.deepcopy(self.original)
        raw = changed["original_csv_base64"]
        changed["original_csv_base64"] = ("A" if raw[0] != "A" else "B") + raw[1:]
        with self.assertRaises(ValueError):
            bind(changed, {self.sha: ledger(self.sha, range(3))})

    def test_missing_csv_fails_closed(self):
        changed = copy.deepcopy(self.original)
        del changed["original_csv_base64"]
        with self.assertRaises(ValueError):
            bind(changed, {})

    def test_unsafe_metadata_or_false_digest_rejected(self):
        for path, value in [
            (("source_sha256",), B),
            (("original_quality", "mainboard_sha256"), B),
            (("publisher_authenticated",), True),
            (("original_quality", "paid_api_calls"), 1),
        ]:
            with self.subTest(path=path):
                changed = copy.deepcopy(self.original)
                obj = changed
                for key in path[:-1]:
                    obj = obj[key]
                obj[path[-1]] = value
                with self.assertRaises(ValueError):
                    bind(changed, {})

    def test_misfiled_other_epoch_is_rejected(self):
        with self.assertRaises(ValueError):
            bind(self.original, {B: ledger(self.sha, range(7))})


if __name__ == "__main__":
    unittest.main()
