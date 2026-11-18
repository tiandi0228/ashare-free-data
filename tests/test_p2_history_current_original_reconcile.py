"""Offline fail-closed contract tests; synthetic replay results are NOT market evidence."""
import copy
import unittest
from collector.p2_history_current_original_reconcile import compare

class Tests(unittest.TestCase):
    def setUp(self):
        self.cp={"phase":"P1_ROSTER_SHARD_LEDGER","source_sha256":"a"*64,
                 "shard_count":400,"completed_shards":44}
        self.h=[{"kind":"PREVIOUSLY_REPORTED_NOT_REPLAYED_THIS_RUN",
                 "reported_day":"2026-11-11",
                 "feature_complete_shards":215,"observed_shards":227}]
        self.replay={"status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
            "source_epoch_sha256":"a"*64,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[],"historical_PIT_verified":False,
            "coverage_certified_for_trading":False,
            "feature_complete_shards":36,"observed_archived_shards":40,
            "archived_original_shards":44}
    def test_no_originals_no_current_claim(self):
        r=compare(self.cp,self.h)
        self.assertEqual(r["status"],"MISSING_CURRENT_ORIGINAL_REPLAY")
        self.assertIsNone(r["current_research_replay"])
        self.assertIsNone(r["project_completion_pct"])
        self.assertFalse(r["cross_epoch_counter_addition_allowed"])
    def test_matching_synthetic_shape_is_only_research(self):
        r=compare(self.cp,self.h,self.replay)
        self.assertEqual(r["current_research_replay"]["feature_complete_shards"],36)
        self.assertEqual(r["historical_report_unreplayed"]["feature_complete_shards"],215)
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["orders"],[])
    def test_epoch_mismatch_not_promoted(self):
        v=copy.deepcopy(self.replay);v["source_epoch_sha256"]="b"*64
        r=compare(self.cp,self.h,v)
        self.assertIsNone(r["current_research_replay"])
        self.assertEqual(r["status"],"SOURCE_EPOCH_MISMATCH_OR_UNVERIFIED")
    def test_rejected_audit_not_promoted(self):
        v=copy.deepcopy(self.replay);v["status"]="REJECTED"
        self.assertIsNone(compare(self.cp,self.h,v)["current_research_replay"])
    def test_originals_cannot_exceed_checkpoint(self):
        v=copy.deepcopy(self.replay);v["archived_original_shards"]=45
        with self.assertRaises(ValueError):compare(self.cp,self.h,v)
    def test_impossible_feature_count_rejected(self):
        v=copy.deepcopy(self.replay);v["feature_complete_shards"]=41
        with self.assertRaises(ValueError):compare(self.cp,self.h,v)
    def test_historical_kind_must_not_claim_verified(self):
        h=copy.deepcopy(self.h);h[0]["kind"]="CURRENT_REPLAY_VERIFIED"
        with self.assertRaises(ValueError):compare(self.cp,h)
    def test_historical_larger_than_total_rejected(self):
        h=copy.deepcopy(self.h);h[0]["observed_shards"]=401
        with self.assertRaises(ValueError):compare(self.cp,h)
    def test_trade_gate_cannot_open(self):
        v=copy.deepcopy(self.replay);v["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):compare(self.cp,self.h,v)
if __name__=="__main__":
    unittest.main()
