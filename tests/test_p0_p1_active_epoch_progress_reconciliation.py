"""Actual same-epoch P0/P1 reconciliation tests, with bounded tampering."""
import copy
import json
import unittest
from pathlib import Path
from collector.p0_p1_active_epoch_progress_reconciliation import reconcile

ROOT=Path(__file__).resolve().parents[1]
def load(path):
    return json.loads((ROOT/path).read_text())
def fixture():
    return (
        load("evidence/p1_active_roster.json"),
        load("evidence/checkpoints/5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022.json"),
        load("evidence/p1_checkpoint.json"),
        load("archived-research/5ba00fbd720fad90/archive_status.json"),
        load("reports/p2_current_full_replay/verified.json")
    )
class ActiveEpochReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=fixture()
    def setUp(self):
        self.args=copy.deepcopy(self.base)
    def must_reject(self,pass_offline=True):
        with self.assertRaises(ValueError):
            reconcile(*self.args,pass_offline)
    def test_active_epoch_241_not_legacy_44(self):
        x=reconcile(*self.args,True)
        self.assertEqual(x["P1"]["active_completed_shards"],241)
        self.assertEqual(x["P1"]["active_coverage_pct"],60.25)
        self.assertEqual(x["P1"]["legacy_alias_completed_shards"],44)
        self.assertFalse(x["P1"]["legacy_alias_is_active_source"])
        self.assertTrue(x["P1"]["original_CSV_replay_verified_in_this_run"])
        self.assertEqual(x["P2_research_feature_complete_shards"],226)
    def test_p0_historical_100_not_production(self):
        x=reconcile(*self.args,True)
        self.assertEqual(x["P0"]["historical_development_pct_reported"],100)
        self.assertIsNone(x["P0"]["current_full_production_acceptance_pct"])
        self.assertFalse(x["P0"]["production_approved"])
        self.assertEqual(x["trade_gate"],"BLOCKED")
        self.assertEqual(x["orders"],[])
    def test_no_p0_offline_acceptance(self):
        self.must_reject(False)
    def test_wrong_active_epoch(self):
        self.args[1]["source_sha256"]="f"*64
        self.must_reject()
    def test_forged_active_completed_shard(self):
        self.args[1]["completed_shards"]=242
        self.must_reject()
    def test_legacy_alias_overwritten_with_active(self):
        self.args[2]=copy.deepcopy(self.args[1])
        self.must_reject()
    def test_archived_shard_count_tamper(self):
        self.args[3]["archived_shards"]=self.args[3]["archived_shards"][:-1]
        self.must_reject()
    def test_archived_shard_membership_tamper(self):
        self.args[3]["archived_shards"][0]=400
        self.must_reject()
    def test_replay_unverified(self):
        self.args[4]["original_CSVs_independently_replayed_in_this_run"]=False
        self.must_reject()
    def test_forged_official_pit(self):
        self.args[4]["historical_PIT_verified"]=True
        self.must_reject()
    def test_forged_trade_gate(self):
        self.args[1]["trade_gate"]="OPEN"
        self.must_reject()
    def test_pinned_roster_original_bytes_tampered(self):
        self.args[0]["original_csv_base64"]="not-base64"
        self.must_reject()
