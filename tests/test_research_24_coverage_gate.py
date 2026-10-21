"""Cross-run 24 distinct issuer source-SHA-only coverage contracts."""
import copy
import json
from pathlib import Path
import unittest
from collector.research_24_coverage_gate import evaluate

ROOT=Path(__file__).resolve().parents[1]/"reports"

class Research24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=json.loads((ROOT/"p1_pilot_16_source_digests_20261021.json").read_text())
        cls.new=json.loads((ROOT/"p1_delisted_8_source_digests_20261021.json").read_text())

    def result(self, old=None, new=None):
        return evaluate(copy.deepcopy(self.old) if old is None else old,
                        copy.deepcopy(self.new) if new is None else new)

    def test_two_independent_original_replay_provenances(self):
        q=self.result()
        self.assertEqual(q["frozen_issuer_count"],24)
        self.assertEqual(q["original_source_rows"],11563)
        self.assertEqual(q["trade_status_1_rows"],11523)
        self.assertEqual(q["trade_status_0_rows"],40)
        self.assertEqual(q["delisted_600421_last_status_1_date"],"2026-06-22")
        self.assertEqual(q["delisted_600421_last_vendor_row_date"],"2026-06-25")
        self.assertEqual(q["trade_gate"],"BLOCKED")
        self.assertEqual(q["candidate_universe"],[])
        self.assertEqual(q["orders"],[])
        self.assertEqual(q["executable_candidates"],[])
        self.assertFalse(q["full_mainboard_historical_backfill_complete"])
        self.assertFalse(q["official_historical_point_in_time_issuer_pool_verified"])
        self.assertFalse(q["all_original_bytes_rechecked_in_this_metadata_only_run"])
        self.assertEqual(len(q["original_sha_receipts"]),24)

    def test_source_code_overlap_rejected(self):
        new=copy.deepcopy(self.new)
        new["replay_report"]["source_receipts"][1]["code"]="sh.600000"
        with self.assertRaisesRegex(ValueError,"duplication"):
            self.result(new=new)

    def test_invalid_source_sha_rejected(self):
        new=copy.deepcopy(self.new)
        new["replay_report"]["source_receipts"][0]["original_csv_sha256"]="tampered"
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            self.result(new=new)

    def test_false_official_pit_rejected(self):
        old=copy.deepcopy(self.old)
        old["audit_report"]["historical_point_in_time_universe_verified"]=True
        with self.assertRaisesRegex(ValueError,"promoted"):
            self.result(old=old)

    def test_delisted_last_trading_status_semantic_rejected(self):
        new=copy.deepcopy(self.new)
        new["replay_report"]["source_receipts"][0]["last_status_1_date"]="2026-06-25"
        with self.assertRaisesRegex(ValueError,"temporal case"):
            self.result(new=new)

    def test_incomplete_eight_source_replay_rejected(self):
        new=copy.deepcopy(self.new)
        new["actual_replay_verified"]=False
        with self.assertRaisesRegex(ValueError,"identity"):
            self.result(new=new)

if __name__=="__main__":
    unittest.main()
