import json
import unittest
from pathlib import Path

from collector.p4_prospective_registration import digest, verify

MANIFEST = Path(__file__).resolve().parents[1] / "manifests/p4_prospective_20261201.json"


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(MANIFEST.read_bytes())

    def test_checked_in_protocol_stays_research_only(self):
        result = verify(self.doc)
        self.assertEqual(result["window_start"], "2026-12-01")
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertFalse(result["prospective_freeze_externally_attested"])
        self.assertFalse(result["baseline_bytes_verified"])

    def test_outer_rehash_cannot_replace_frozen_parameters(self):
        r = self.doc["registration"]
        r["protocol"]["frozen_strategy_rules"]["target_fraction"] = "0.06"
        self.doc["registration_sha256"] = digest(r)
        with self.assertRaisesRegex(ValueError, "protocol fingerprint"):
            verify(self.doc)

    def test_beijing_same_day_is_not_pre_window(self):
        r = self.doc["registration"]
        r["protocol"]["claimed_created_at_utc"] = "2026-11-30T16:00:00Z"
        r["protocol_sha256"] = digest(r["protocol"])
        self.doc["registration_sha256"] = digest(r)
        with self.assertRaisesRegex(ValueError, "Beijing time"):
            verify(self.doc)

    def test_wrong_baseline_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, "baseline bytes"):
            verify(self.doc, b"{}")

    def test_rehashed_baseline_cannot_claim_oos_or_cross_boundary(self):
        import hashlib

        r = self.doc["registration"]
        base = {"status": "VENDOR_REPLAY_NOT_CERTIFIED_OOS",
                "archive_commit_sha": r["baseline_archive_commit"],
                "epoch": r["baseline_archive_epoch"], "trade_gate": "BLOCKED",
                "orders": [], "executable_candidates": [],
                "historical_OOS_validated": False, "validation_end": "2026-10-20"}
        for change in ({"historical_OOS_validated": True}, {"validation_end": "2026-12-01"}, {}):
            with self.subTest(change=change):
                raw = json.dumps(dict(base, **change)).encode()
                r["protocol"]["negative_baseline_artifact_sha256"] = hashlib.sha256(raw).hexdigest()
                r["protocol_sha256"] = digest(r["protocol"])
                self.doc["registration_sha256"] = digest(r)
                if change:
                    with self.assertRaisesRegex(ValueError, "frozen research scope"):
                        verify(self.doc, raw)
                else:
                    self.assertTrue(verify(self.doc, raw)["baseline_bytes_verified"])
