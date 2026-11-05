"""Chronology-only split tests; no market/backtest performance claims."""
import unittest
from collector.p2_purged_oos_partition import partition,contract_summary

def item(id,feature,label_start,label_end,source="ARCHIVED_VENDOR_RESEARCH_UNVERIFIED"):
    return {"id":id,"source":source,"feature_asof":feature,
            "label_start":label_start,"label_end":label_end}

class PurgedPartitionTests(unittest.TestCase):
    def test_split_purges_train_label_leak_and_holdout_censoring(self):
        rows=[
          item("train","2026-01-02","2026-01-03","2026-01-05"),
          item("leak","2026-01-07","2026-01-09","2026-01-15"),
          item("embargo","2026-01-12","2026-01-13","2026-01-15"),
          item("holdout","2026-01-20","2026-01-21","2026-01-23"),
          item("censored","2026-02-01","2026-02-02","2026-02-06"),
        ]
        r=partition(rows,"2026-01-10","2026-01-20","2026-02-03",5)
        self.assertEqual(r["status"],"TIME_WINDOWS_PURGED_NOT_HISTORICAL_OOS_CERTIFICATION")
        self.assertEqual(r["training_event_ids"],["train"])
        self.assertEqual(r["holdout_event_ids"],["holdout"])
        self.assertEqual(r["purged_count"],3)
        self.assertFalse(r["historical_OOS_validated"])
        self.assertFalse(r["parameters_frozen_before_holdout_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_closed_embargo_and_missing_valid_fold_rejected(self):
        rows=[item("a","2026-01-01","2026-01-02","2026-01-03"),
              item("b","2026-01-20","2026-01-21","2026-01-22")]
        for end,start,gap in [
            ("2026-01-15","2026-01-20",5),
            ("2026-01-20","2026-01-15",0),
            ("2026-01-15","2026-01-15",0),
        ]:
            self.assertEqual(partition(rows,end,start,"2026-02-01",gap)["status"],"REJECTED")
        self.assertEqual(partition(rows,"2026-01-10","2026-01-20","2026-02-01",5)["train_count"],1)
    def test_fake_sources_duplicate_ids_and_future_before_feature_rejected(self):
        rows=[item("a","2026-01-01","2026-01-02","2026-01-03"),
              item("b","2026-01-20","2026-01-21","2026-01-22")]
        for variant in [
            [rows[0],dict(rows[1],id="a")],
            [rows[0],dict(rows[1],source="REAL_CERTIFIED_MARKET")],
            [dict(rows[0],label_start="2025-12-31"),rows[1]],
            [dict(rows[0],label_end="2026-01-01"),rows[1]],
        ]:
            q=partition(variant,"2026-01-10","2026-01-20","2026-02-01",5)
            self.assertEqual(q["status"],"REJECTED")
            self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_strict_calendar_window_not_claim_exchange_sessions(self):
        rows=[item("a","2026-01-01","2026-01-02","2026-01-03",
                   source="SYNTHETIC_OFFLINE_FIXTURE"),
              item("b","2026-01-20","2026-01-21","2026-01-22",
                   source="SYNTHETIC_OFFLINE_FIXTURE")]
        q=partition(rows,"2026-01-10","2026-01-20","2026-02-01",5)
        self.assertFalse(q["full_historical_universe_verified"])
        self.assertFalse(q["strategy_returns_or_win_rate_certified"])
        self.assertEqual(q["orders"],[])
        self.assertFalse(contract_summary()["strategy_OOS_performance_verified"])

if __name__=="__main__":unittest.main()
