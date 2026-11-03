"""Offline sample reliability tests: never substitute stale good prices."""
import unittest
from collector.intraday_source_health import source_health
from collector.intraday_snapshot_archive import WATCHLIST

def sample(run, failed=(), issues=()):
    return {
        "run_id":run,
        "symbols":{c:{
            "status":"SOURCE_UNAVAILABLE" if c in failed else "RESEARCH_ONLY",
            "error_stage":"EASTMONEY_MINUTES" if c in failed else None,
            "error_type":"URLError" if c in failed else None,
            "quality_issues":[] if c in failed else list(issues),
        } for c in WATCHLIST},
    }

class SourceHealthTests(unittest.TestCase):
    def test_failure_recovery_and_latest_failure(self):
        rows=[sample(1),sample(2,failed=("002249",)),
              sample(3,failed=("002249",)),
              sample(4),sample(5,failed=("002249",))]
        h=source_health(rows)["002249"]
        self.assertEqual(h["samples"],5)
        self.assertEqual(h["research_snapshots"],2)
        self.assertEqual(h["source_failures"],3)
        self.assertEqual(h["max_consecutive_sample_failures"],2)
        self.assertEqual(h["consecutive_failures_at_latest_sample"],1)
        self.assertEqual(h["recoveries_after_failed_sample"],1)
        self.assertEqual(h["last_failed_run"],5)
        self.assertEqual(h["failure_stages"],{"EASTMONEY_MINUTES":3})
        self.assertEqual(h["error_types"],{"URLError":3})
        self.assertEqual(h["latest_status"],"SOURCE_UNAVAILABLE")
        self.assertFalse(h["provider_sla_certified"])
        self.assertFalse(h["cross_source_price_verified"])
        self.assertEqual(h["trade_gate"],"BLOCKED")

    def test_issues_count_distinct_runs_not_duplicates(self):
        rows=[sample(1,issues=("QUOTE_STALE_OR_FUTURE",
                               "QUOTE_STALE_OR_FUTURE")),
              sample(2,issues=("QUOTE_STALE_OR_FUTURE",))]
        self.assertEqual(source_health(rows)["002249"]["quality_issue_samples"],
                         {"QUOTE_STALE_OR_FUTURE":2})

    def test_unaffected_stock_remains_successful(self):
        rows=[sample(1,failed=("002249",)),sample(2)]
        healthy=source_health(rows)["300015"]
        self.assertEqual(healthy["research_snapshots"],2)
        self.assertEqual(healthy["source_failures"],0)
        self.assertEqual(healthy["observed_sample_success_ratio"],1)

    def test_fails_closed_on_invalid_status_or_missing_rows(self):
        with self.assertRaises(ValueError):source_health([])
        row=sample(1)
        row["symbols"]["002249"]["status"]="READY_TO_BUY"
        with self.assertRaises(ValueError):source_health([row])
        row=sample(1)
        del row["symbols"]["300015"]
        with self.assertRaises(ValueError):source_health([row])

if __name__=="__main__":unittest.main()
