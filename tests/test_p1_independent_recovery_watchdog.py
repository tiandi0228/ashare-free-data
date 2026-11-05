"""An independent P1 schedule cannot circumvent the existing at-most-once guard."""
import re
import unittest
from pathlib import Path

FILE=Path(".github/workflows/p1-independent-recovery-watchdog.yml")

class IndependentRecoveryWatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=FILE.read_text(encoding="utf-8")
    def test_only_approved_weekday_followup_slots(self):
        self.assertEqual(re.findall(r"cron: '([^']+)'",self.workflow),
                         ["32 1,2,4,6,8,10,12,14 * * 1-5"])
        self.assertIn("cancel-in-progress: false",self.workflow)
    def test_explicit_write_permission_not_pr_dispatch(self):
        self.assertIn("contents: write",self.workflow)
        self.assertIn("actions: write",self.workflow)
        self.assertIn("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'",
                      self.workflow)
        self.assertNotIn("github.event_name == 'pull_request' ||",self.workflow)
        self.assertIn("github.event_name == 'push' && github.ref == 'refs/heads/main'",self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'",self.workflow)
        self.assertIn("github.event_name == 'schedule'",self.workflow)
        self.assertNotIn("github.event_name == 'pull_request' ||",self.workflow)
        self.assertIn("needs: verify",self.workflow)
    def test_existing_fail_closed_chain_required(self):
        positions=[]
        for module in ("p1_schedule_watchdog","p1_safe_recovery",
                       "p1_recovery_claim","p1_recovery_dispatch_preflight",
                       "p1_recovery_dispatch_once",
                       "p1_recovery_run_reconciliation"):
            needle="python -m collector."+module+" "
            self.assertIn(needle,self.workflow)
            positions.append(self.workflow.index(needle))
        self.assertEqual(positions,sorted(positions))
        self.assertIn("P1_RECOVERY_EXECUTION_ENABLED: 'true'",self.workflow)
        self.assertIn("--preflight evidence/p1/preflight.json",self.workflow)
        self.assertIn("p1-independent-recovery-${{ github.run_id }}",self.workflow)
    def test_no_new_orders_or_bypass(self):
        self.assertNotIn("shards_per_run: '2'",self.workflow)
        self.assertNotIn("trade_gate: OPEN",self.workflow)

if __name__=="__main__":
    unittest.main()
