"""P4 cannot certify trading from four replayed files alone."""
import json,unittest
from pathlib import Path
from collector.p4_real_source_readiness import assess,FILENAMES,REPORTS
class ReadinessTests(unittest.TestCase):
 def test_real_sources_leave_actual_validation_blocked(self):
    docs=[json.loads((REPORTS/n).read_text()) for n in FILENAMES]
    q=assess(docs[2],docs)
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
if __name__=="__main__":unittest.main()
