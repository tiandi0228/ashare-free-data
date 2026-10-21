"""Cross-run 24/24 original SHA replay audit must be factual and research-only."""
import copy
import json
from pathlib import Path
import unittest
from collector.audit_24_reacquisition import audit

ROOT=Path(__file__).resolve().parents[1]/"reports"


class FullPilotRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports=[
            json.loads((ROOT/name).read_text(encoding="utf-8"))
            for name in (
                "p1_research_24_coverage_20261021.json",
                "p1_reacquire_16_batches_01_20261021.json",
                "p1_reacquire_8_of_24_batch_2_20261021.json",
            )
        ]

    def check(self,mutate=None):
        three=copy.deepcopy(self.reports)
        if mutate:
            mutate(three)
        return audit(*three)

    def test_real_24_independently_anchored_sha_receipts_reconciled(self):
        r=self.check()
        self.assertEqual(r["status"],"24_FROZEN_RESEARCH_SOURCE_BYTES_IDENTICAL_AT_CAPTURE_TIME")
        self.assertEqual(r["matching_issuers"],24)
        self.assertEqual(r["verified_reacquired_rows"],11563)
        self.assertEqual(r["number_of_independent_capped_batches"],3)
        self.assertEqual(len(r["frozen_source_sha_receipts"]),24)
        self.assertTrue(r["all_24_original_bytes_rechecked_on_new_source_calls"])
        self.assertFalse(r["source_raw_originals_permanently_archived"])
        self.assertFalse(r["vendor_historical_revisions_impossible"])
        self.assertFalse(r["complete_mainboard_PIT_verified"])
        self.assertFalse(r["p4_actual_OOS_validated"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["candidate_universe"],[])
        self.assertEqual(r["paid_api_calls"],0)

    def test_one_original_source_SHA_revision_blocks(self):
        def change(x):
            x[1]["verified_source_batches"][0]["source_entries"][0]["current_source_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"hash"):
            self.check(change)

    def test_fake_permanent_original_archive_claim_blocks(self):
        def change(x):
            x[2]["original_comparison"]["original_raw_CSV_durably_archived"]=True
        with self.assertRaisesRegex(ValueError,"temporary"):
            self.check(change)

    def test_deleted_issuer_record_blocks(self):
        def change(x):
            x[1]["verified_source_batches"][1]["source_entries"].pop()
        with self.assertRaisesRegex(ValueError,"Eight issuer"):
            self.check(change)

    def test_duplicate_issuer_identity_blocks(self):
        def change(x):
            r=x[1]["verified_source_batches"][0]["source_entries"]
            r[1]["code"]=r[0]["code"]
        with self.assertRaisesRegex(ValueError,"order drift"):
            self.check(change)

    def test_false_original_source_PIT_authority_blocks(self):
        def change(x):
            x[0]["audit_report"]["official_historical_point_in_time_issuer_pool_verified"]=True
        with self.assertRaisesRegex(ValueError,"not eligible"):
            self.check(change)

    def test_not_all_bytes_same_cannot_be_promoted(self):
        def change(x):
            x[2]["original_comparison"]["source_entries"][1]["sha256_matches_frozen_original"]=False
        with self.assertRaisesRegex(ValueError,"hash"):
            self.check(change)

    def test_forged_source_run_or_trade_state_blocks(self):
        def change(x):
            x[1]["capture_run_id"]=123
        with self.assertRaisesRegex(ValueError,"two-batch"):
            self.check(change)
        def trade(x):
            x[2]["original_comparison"]["trade_gate"]="READY"
        with self.assertRaisesRegex(ValueError,"temporary"):
            self.check(trade)


if __name__=="__main__":
    unittest.main()
