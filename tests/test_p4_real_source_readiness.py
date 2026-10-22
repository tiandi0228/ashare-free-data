"""P4 cannot certify trading from four replayed files alone."""
import json,unittest
from pathlib import Path
from collector.p4_real_source_readiness import assess,FILENAMES,REPORTS,snapshot_age
class ReadinessTests(unittest.TestCase):
 def test_real_sources_leave_actual_validation_blocked(self):
    docs=[json.loads((REPORTS/n).read_text()) for n in FILENAMES]
    q=assess(docs[2],docs,as_of_date="2026-10-22")
    self.assertEqual(q["snapshot_latest_filename_date"],"2026-10-22")
    self.assertEqual(q["snapshot_latest_filename_age_days"],0)
    self.assertFalse(q["snapshot_date_is_source_publication_proof"])
    self.assertEqual(q["verified_conditions"],1)
    self.assertEqual(q["evidence_mode"],"FROZEN_REPOSITORY_SNAPSHOT")
    self.assertEqual(q["evidence_report_files"],list(FILENAMES))
    self.assertFalse(q["independent_live_source_reverification_in_this_run"])
    self.assertFalse(q["latest_market_coverage_verified_in_this_run"])
    self.assertEqual(q["required_conditions"],6)
    self.assertEqual(len(q["missing_conditions"]),5)
    self.assertEqual(q["original_sources_independently_matched"],4)
    self.assertFalse(q["full_market_backtest_performed_in_this_audit"])
    self.assertEqual(q["trade_gate"],"BLOCKED")
    self.assertEqual(q["orders"],[])
 def test_snapshot_ages_without_freshness_claim(self):
    self.assertEqual(snapshot_age("2026-10-25")["snapshot_latest_filename_age_days"],3)
    with self.assertRaisesRegex(ValueError,"future"):
        snapshot_age("2026-10-20")
if __name__=="__main__":unittest.main()
