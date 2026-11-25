"""P2 200+ historical feature shards are distinct from engineering 30%."""
import copy
import json
import unittest
from pathlib import Path

from collector.p2_separated_progress_report import summarize

HISTORY=Path(__file__).resolve().parents[1]/"evidence/p2_prior_reported_feature_shard_history.json"

def engineering():
    rows=[{"id":f"criterion_{i}","weight":10,"passed":i<3} for i in range(10)]
    return {
        "phase":"STOCKMATE_P2_P4_ENGINEERING_BASELINE",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "orders":[],"executable_candidates":[],"tests_executed":True,
        "stages":{"P2":{"criteria":rows,"engineering_acceptance_baseline_pct":30}}
    }

class SeparateP2Tests(unittest.TestCase):
    def setUp(self):
        self.base=engineering()
        self.historical=json.loads(HISTORY.read_text())

    def report(self):
        return summarize(self.base,self.historical)

    def test_separate_30pct_from_215_shards(self):
        result=self.report()
        self.assertEqual(result["P2_offline_engineering_pct"],30)
        last=result["P2_latest_historical_report"]
        self.assertEqual(last["feature_complete_shards"],215)
        self.assertEqual(last["observed_shards"],227)
        self.assertEqual(last["feature_coverage_pct"],94.71)
        self.assertEqual(last["evidence_status"],"HISTORICAL_REPORTED_UNREPLAYED")
        self.assertIsNone(result["P2_current_feature_coverage"])
        self.assertIsNone(result["P2_overall_project_completion_pct"])
        self.assertFalse(result["P2_progress_regression_proven"])

    def test_earlier_200_count_retained(self):
        self.assertTrue(any(x["feature_complete_shards"]==200 for x in self.report()["P2_historical_feature_observations"]))

    def test_reject_forged_current_status_label(self):
        self.historical[-1]["kind"]="CURRENT_VERIFIED"
        with self.assertRaises(ValueError):self.report()

    def test_reject_overflow(self):
        self.historical[-1]["feature_complete_shards"]=228
        with self.assertRaises(ValueError):self.report()

    def test_reject_unsafe_engineering_baseline(self):
        self.base["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):self.report()

    def test_reject_forged_engineering_success(self):
        self.base["stages"]["P2"]["engineering_acceptance_baseline_pct"]=100
        with self.assertRaises(ValueError):self.report()

    def test_current_report_requires_real_replay(self):
        current={
            "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
            "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
            "trade_gate":"BLOCKED","historical_PIT_verified":False,
            "orders":[],"executable_candidates":[],
            "coverage_certified_for_trading":False,
            "feature_complete_shards":215,
            "observed_archived_shards":227,
            "observed_with_feature_gaps_shards":12,
        }
        with self.assertRaises(ValueError): summarize(self.base,self.historical,current)

    def test_exact_verified_current_report_distinct(self):
        current={
            "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
            "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
            "trade_gate":"BLOCKED","historical_PIT_verified":False,
            "orders":[],"executable_candidates":[],
            "coverage_certified_for_trading":False,
            "original_csv_sha_replay_verified_in_this_run":True,
            "feature_complete_shards":5,
            "observed_archived_shards":6,
            "observed_with_feature_gaps_shards":1,
        }
        r=summarize(self.base,self.historical,current)
        self.assertEqual(r["P2_current_feature_coverage"]["feature_coverage_pct"],83.33)
        self.assertEqual(r["P2_latest_historical_report"]["feature_complete_shards"],215)
