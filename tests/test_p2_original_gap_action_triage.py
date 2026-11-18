"""Fail-closed P2 feature gap action queue, synthetic safety fixtures."""
import copy
import unittest
from collector.p2_original_gap_action_triage import EPOCH, triage

def fixture():
    queue=[]
    categories=[]
    indices=[27,33,78,97,104,120,137,140,161,166,182,186,208,378,379]
    for i,index in enumerate(indices):
        items=[]
        for j in range(2 if i==0 else 1):
            is_short=index==97
            code=("sh" if index<300 else "sz")+f".{600000+i*50+j if index<300 else 200000+i*50+j:06d}"
            category="FEWER_THAN_21_VENDOR_ROWS_ASOF" if is_short else "VENDOR_SUSPENDED_IN_LAST_21_ROWS"
            categories.append(category)
            items.append({
                "issuer":code,"reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS",
                "original_gap_diagnostic":{
                    "category":category,"vendor_rows_at_or_before_asof":18 if is_short else 485,
                    "last_21_vendor_rows_suspended":0 if is_short else 3,
                    "first_vendor_row_day":"2026-09-17" if is_short else "2024-10-21",
                    "last_vendor_row_day":"2026-10-20",
                    "exact_asof_vendor_row_present":True,
                    "original_csv_sha256":f"{1000+i*10+j:064x}",
                    "vendor_calendar_independently_verified":False,
                    "historical_PIT_verified":False,"repair_approved":False,
                }})
        queue.append({"shard_id":f"shard_{index:04d}",
                      "issuer_gap_count":len(items),"issuer_reasons":items})
    assert len(categories)==16
    return {
        "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
        "source_epoch_sha256":EPOCH,
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "coverage_certified_for_trading":False,
        "orders":[],"executable_candidates":[],
        "gap_repair_queue_is_research_only":True,
        "checkpoint_completed_shards":241,
        "observed_archived_shards":241,"feature_complete_shards":226,
        "observed_with_feature_gaps_shards":15,"unobserved_archived_shards":0,
        "issuer_evidence_gap_count":16,
        "gap_repair_queue":queue,
        "gap_shard_ids":[x["shard_id"] for x in queue],
        "gap_reason_counts":{"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":16},
    }

class GapTriageTests(unittest.TestCase):
    def setUp(self):
        self.data=fixture()

    def expect_reject(self):
        with self.assertRaises(ValueError):triage(self.data)

    def test_safe_exact_16_gap_classification(self):
        result=triage(self.data)
        self.assertEqual(result["reason_counts"],{
            "VENDOR_SUSPENDED_IN_LAST_21_ROWS":15,
            "FEWER_THAN_21_VENDOR_ROWS_ASOF":1})
        self.assertEqual(result["unresolved_shards"],15)
        self.assertEqual(result["unresolved_issuers"],16)
        self.assertEqual(result["feature_complete_shards"],226)
        self.assertEqual(result["complete_feature_shards_promoted_by_triage"],0)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_short_history_never_backfilled(self):
        rows=triage(self.data)["research_actions"]
        short=[x for x in rows if x["category"]=="FEWER_THAN_21_VENDOR_ROWS_ASOF"]
        self.assertEqual(len(short),1)
        self.assertEqual(short[0]["vendor_rows"],18)
        self.assertFalse(short[0]["original_mutation_authorized"])

    def test_forged_feature_completion_rejected(self):
        self.data["feature_complete_shards"]=227
        self.expect_reject()

    def test_duplicated_issuer_rejected(self):
        self.data["gap_repair_queue"][1]["issuer_reasons"][0]["issuer"]=self.data["gap_repair_queue"][0]["issuer_reasons"][0]["issuer"]
        self.expect_reject()

    def test_forged_source_epoch_rejected(self):
        self.data["source_epoch_sha256"]="0"*64
        self.expect_reject()

    def test_no_trade_gate_override(self):
        self.data["trade_gate"]="OPEN"
        self.expect_reject()

    def test_forged_official_calendar_rejected(self):
        self.data["gap_repair_queue"][0]["issuer_reasons"][0]["original_gap_diagnostic"]["vendor_calendar_independently_verified"]=True
        self.expect_reject()

    def test_short_history_cannot_be_21(self):
        self.data["gap_repair_queue"][3]["issuer_reasons"][0]["original_gap_diagnostic"]["vendor_rows_at_or_before_asof"]=21
        self.expect_reject()

    def test_suspended_category_requires_positive_count(self):
        self.data["gap_repair_queue"][0]["issuer_reasons"][0]["original_gap_diagnostic"]["last_21_vendor_rows_suspended"]=0
        self.expect_reject()

    def test_reject_changed_source_sha(self):
        self.data["gap_repair_queue"][0]["issuer_reasons"][0]["original_gap_diagnostic"]["original_csv_sha256"]="bad"
        self.expect_reject()

    def test_gap_shard_identity_must_match(self):
        self.data["gap_shard_ids"][0]="shard_0001"
        self.expect_reject()

    def test_reject_duplicate_shard(self):
        self.data["gap_repair_queue"][1]["shard_id"]=self.data["gap_repair_queue"][0]["shard_id"]
        self.expect_reject()
