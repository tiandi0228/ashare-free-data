"""SHA-bound P3/P4 vendor halt research handoff; never authenticates fills."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p3_p4_official_halt_gap_manifest import build

CODE = "sh.600150"
DIGEST = "a" * 64


def entry(*, digest=DIGEST, entry_day="2025-08-11"):
    return {"code": CODE, "entry_date": entry_day,
            "target_exit_date": "2025-08-14", "vendor_status": "0",
            "original_csv_sha256": digest, "official_halt_verified": False}


def report(items):
    return {"verified_issuers": 1, "target_vendor_suspended": len(items),
            "vendor_halt_crosscheck_queue": items}


class HaltGapReceiptTests(unittest.TestCase):
    def test_sha_bound_single_gap_is_research_only(self):
        with patch("collector.p3_p4_official_halt_gap_manifest.audit", return_value=report([entry()])):
            result = build("unused")
        self.assertEqual(result["distinct_issuer_halt_dates"], 1)
        record = result["pending_official_evidence"][0]
        self.assertEqual(record["original_csv_sha256"], DIGEST)
        self.assertFalse(record["official_effective_date_authenticated"])
        self.assertEqual(result["officially_certified_halt_dates"], 0)
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_duplicate_same_source_collapses_but_preserves_observations(self):
        with patch("collector.p3_p4_official_halt_gap_manifest.audit", return_value=report(
                [entry(), entry(entry_day="2025-08-12")])):
            result = build("unused")
        self.assertEqual(result["distinct_issuer_halt_dates"], 1)
        self.assertEqual(result["vendor_suspended_exit_observations"], 2)
        self.assertEqual(len(result["pending_official_evidence"][0]["affected_entry_dates"]), 2)

    def test_conflicting_original_sha_rejected(self):
        with patch("collector.p3_p4_official_halt_gap_manifest.audit", return_value=report(
                [entry(), entry(digest="b" * 64)])):
            with self.assertRaisesRegex(ValueError, "conflicting original"):
                build("unused")

    def test_missing_forged_or_unofficial_source_is_rejected(self):
        for kwargs in (
            {"digest": None},
            {"digest": "not-a-sha"},
        ):
            with self.subTest(kwargs=kwargs):
                with patch("collector.p3_p4_official_halt_gap_manifest.audit",
                           return_value=report([entry(**kwargs)])):
                    with self.assertRaises(ValueError):
                        build("unused")
        bad = entry()
        bad["official_halt_verified"] = True
        with patch("collector.p3_p4_official_halt_gap_manifest.audit", return_value=report([bad])):
            with self.assertRaises(ValueError):
                build("unused")

    def test_real_integrity_join_sha_from_archive_fixture(self):
        # Historical target vendor status is a research clue, never a fill.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "epoch" / "shard_0000"
            folder.mkdir(parents=True)
            raw = (
                "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n"
                "2025-08-11,sh.600150,38.5,38.5,38.5,38.5,100,3850,3,1\n"
                "2025-08-14,sh.600150,38.5,38.5,38.5,38.5,,,3,0\n"
            ).encode()
            (folder / "sh_600150.csv").write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            (folder / "quality.json").write_text(json.dumps({
                "status": "OBSERVED_SUBSET_UNVERIFIED", "trade_gate": "BLOCKED",
                "orders": [], "historical_point_in_time_universe_verified": False,
                "issuer_count": 1,
                "results": [{"code": CODE, "status": "OBSERVED_UNVERIFIED",
                             "rows": 2, "tradable_rows": 1, "suspended_status_rows": 1,
                             "sha256": digest}]
            }))
            with patch("collector.p4_real_exit_availability.research_exit",
                       return_value={"candidate_earlier_exit": "2025-08-14"}):
                result = build(tmp)
            self.assertEqual(result["vendor_suspended_exit_observations"], 1)
            self.assertEqual(result["pending_official_evidence"][0]["original_csv_sha256"], digest)
            self.assertFalse(result["historical_PIT_trade_eligible"])
            self.assertEqual(result["executable_candidates"], [])


if __name__ == "__main__":
    unittest.main()
