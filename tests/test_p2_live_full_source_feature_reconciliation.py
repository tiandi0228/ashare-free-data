"""P2 live 242+ original CSV replay summary must reconcile exact source SHA."""
import copy
import json
import unittest
from pathlib import Path
from collector.p2_live_full_source_feature_reconciliation import reconcile,EPOCH

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"evidence/checkpoints"/(EPOCH+".json")
REFS={k:"a"*40 for k in ("checkpoint","original_csv_archive","feature_receipts")}

def fixture():
    ledger=json.loads(SOURCE.read_text())
    original={
        "source_sha256":EPOCH,"trade_gate":"BLOCKED",
        "archived_shards":[row["index"] for row in ledger["completed"]],
    }
    shard_ids=[f"shard_{x['index']:04d}" for x in ledger["completed"]]
    published={
        "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
        "source_epoch_sha256":EPOCH,
        "checkpoint_completed_shards":ledger["completed_shards"],
        "checkpoint_total_shards":ledger["shard_count"],
        "archived_original_shards":ledger["completed_shards"],
        "coverage_report_count":94,
        "observed_archived_shards":ledger["completed_shards"],
        "feature_complete_shards":ledger["completed_shards"]-15,
        "observed_with_feature_gaps_shards":15,
        "unobserved_archived_shards":0,
        "observed_shard_ids":shard_ids,
        "unobserved_shard_ids":[],
        "gap_shard_ids":shard_ids[:15],
        "feature_issuer_count":ledger["completed_issuers"]-16,
        "issuer_evidence_gap_count":16,
        "observed_feature_or_gap_issuers":ledger["completed_issuers"],
        "unobserved_issuer_count":0,
        "gap_reason_counts":{"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":16},
        "gap_issuer_codes":[],
        "gap_repair_queue":[],
        "full_archive_evidence_accounted":True,
        "full_archive_feature_coverage":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "historical_PIT_verified":False,
        "coverage_certified_for_trading":False,
        "full_market_universe_verified":False,
    }
    return [copy.deepcopy(published),copy.deepcopy(published),ledger,original,copy.deepcopy(REFS)]

class LiveReplayTests(unittest.TestCase):
    def setUp(self):
        self.args=fixture()
    def result(self):
        return reconcile(*self.args)
    def reject(self):
        with self.assertRaises(ValueError):self.result()
    def test_fixed_241_source_control_is_valid_research_only(self):
        r=self.result()
        self.assertEqual(r["accepted_main_shards"],241)
        self.assertEqual(r["P2_feature_complete_shards"],226)
        self.assertEqual(r["P2_feature_coverage_pct"],93.78)
        self.assertFalse(r["historical_PIT_verified"])
        self.assertFalse(r["trading_authorized"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_next_same_epoch_shard_242_and_feature_receipt(self):
        ledger=self.args[2]
        index=376
        self.assertNotIn(index,self.args[3]["archived_shards"])
        row={"index":index,"issuer_count":8,"manifest_sha256":"e"*64,"receipt_sha256":"f"*64}
        ledger["completed"].append(row)
        ledger["completed_shards"]+=1
        ledger["completed_issuers"]+=8
        ledger["pending_shards"].remove(index)
        ledger["next_shard"]=min(ledger["pending_shards"])
        self.args[3]["archived_shards"].append(index)
        for i in (0,1):
            data=self.args[i]
            data["checkpoint_completed_shards"]+=1
            data["archived_original_shards"]+=1
            data["observed_archived_shards"]+=1
            data["feature_complete_shards"]+=1
            data["coverage_report_count"]+=1
            data["feature_issuer_count"]+=8
            data["observed_feature_or_gap_issuers"]+=8
            data["observed_shard_ids"].append("shard_0376")
        r=self.result()
        self.assertEqual(r["accepted_main_shards"],242)
        self.assertEqual(r["P1_coverage_pct"],60.5)
        self.assertEqual(r["P2_feature_complete_shards"],227)
        self.assertEqual(r["P2_feature_coverage_pct"],93.8)
        self.assertEqual(r["unresolved_feature_gap_shards"],15)
        self.assertEqual(r["feature_receipts_replayed"],95)
    def test_missing_original_archive_shard_is_blocking(self):
        self.args[3]["archived_shards"].pop()
        self.reject()
    def test_wrong_live_original_epoch_rejected(self):
        self.args[3]["source_sha256"]="b"*64
        self.reject()
    def test_mismatched_feature_count_rejected(self):
        self.args[0]["feature_complete_shards"]-=1
        self.reject()
    def test_fake_published_feature_replay_rejected(self):
        self.args[1]["feature_complete_shards"]+=1
        self.reject()
    def test_original_issuer_count_mismatch_rejected(self):
        self.args[0]["observed_feature_or_gap_issuers"]-=1
        self.reject()
    def test_disabled_trade_gate_required(self):
        self.args[0]["trade_gate"]="OPEN"
        self.reject()
    def test_historical_pit_promotion_rejected(self):
        self.args[1]["historical_PIT_verified"]=True
        self.reject()
    def test_missing_receipts_rejected(self):
        self.args[0]["coverage_report_count"]=0
        self.reject()
    def test_wrong_feature_receipt_git_sha_rejected(self):
        self.args[4]["feature_receipts"]="wrong"
        self.reject()
    def test_duplicate_checkpoint_archive_indices_rejected(self):
        self.args[3]["archived_shards"][0]=self.args[3]["archived_shards"][1]
        self.reject()
    def test_live_summary_gap_queue_difference_rejected(self):
        self.args[1]["gap_repair_queue"]=[{"untrusted":True}]
        self.reject()
