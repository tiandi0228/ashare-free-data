"""Pinned vendor roster cannot certify active market coverage or trades."""
import unittest
from collector.p1_roster_checkpoint_binding import bind
from tests.test_p1_epoch_status import ledger

A = "a" * 64
B = "b" * 64


def roster(sha=A):
    return {
        "phase": "P1_PINNED_VENDOR_ROSTER_RESEARCH_ONLY",
        "publisher_authenticated": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
        "source_sha256": sha,
        "original_quality": {
            "phase": "P1_FRESH_VENDOR_ROSTER",
            "status": "FROZEN_VENDOR_SNAPSHOT_UNVERIFIED",
            "publisher_authenticated": False,
            "historical_PIT_verified": False,
            "trade_gate": "BLOCKED",
            "orders": [],
            "executable_candidates": [],
            "paid_api_calls": 0,
            "mainboard_sha256": sha,
        },
    }


class BindingTests(unittest.TestCase):
    def test_matching_epoch_is_research_only(self):
        report=bind(roster(), {B:ledger(B,range(82)), A:ledger(A,range(163))})
        self.assertEqual(report["status"], "MATCHED_UNVERIFIED_RESEARCH_EPOCH")
        self.assertEqual(report["matched_epoch"], A)
        self.assertEqual(report["completed_shards"], 163)
        self.assertEqual(report["checkpoint_percent"], 40.75)
        self.assertFalse(report["historical_PIT_verified"])
        self.assertFalse(report["full_market_bars_certified"])
        self.assertEqual(report["orders"], [])
        self.assertEqual(report["trade_gate"], "BLOCKED")

    def test_nonmatching_source_never_falls_back_to_highest_count(self):
        result=bind(roster(), {B:ledger(B,range(200))})
        self.assertEqual(result["status"], "PINNED_EPOCH_CHECKPOINT_MISSING")
        self.assertIsNone(result["matched_epoch"])
        self.assertIsNone(result["checkpoint_percent"])

    def test_mismatched_quality_digest_or_unsafe_roster_rejected(self):
        r=roster()
        r["original_quality"]["mainboard_sha256"]=B
        with self.assertRaises(ValueError):bind(r,{A:ledger(A,range(5))})
        r=roster()
        r["publisher_authenticated"]=True
        with self.assertRaises(ValueError):bind(r,{})
        r=roster()
        r["original_quality"]["paid_api_calls"]=1
        with self.assertRaises(ValueError):bind(r,{})

    def test_bad_other_epoch_cannot_be_silently_ignored(self):
        with self.assertRaises(ValueError):
            bind(roster(), {A:ledger(B,range(7))})


if __name__ == "__main__":
    unittest.main()
