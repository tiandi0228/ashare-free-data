"""Crosswalk workflow must follow the validated active P1 checkpoint, never a frozen epoch."""
import unittest
from pathlib import Path

WORKFLOW=Path(__file__).resolve().parents[1]/".github/workflows/p2-p3-original-gap-crosswalk.yml"

class CrosswalkCurrentEpochTests(unittest.TestCase):
    def test_resolves_validated_active_roster_before_reading_coverage(self):
        text=WORKFLOW.read_text()
        self.assertIn("python -m collector.p1_active_migration_checkpoint",text)
        self.assertIn("--github-output \"$GITHUB_OUTPUT\"",text)
        self.assertIn('EPOCH="${{ steps.pin.outputs.source_epoch }}"',text)
        self.assertIn('PREFIX="${EPOCH:0:16}"',text)
        self.assertIn('git show "FETCH_HEAD:summaries/$PREFIX.json"',text)
        self.assertNotIn("FETCH_HEAD:summaries/5ba00fbd720fad90.json",text)
    def test_rejects_stale_checkpoint_and_unsafe_coverage(self):
        text=WORKFLOW.read_text()
        self.assertIn("coverage.get('source_epoch_sha256')!=active['source_sha256']",text)
        self.assertIn("coverage.get('checkpoint_completed_shards')!=active['completed_shards']",text)
        self.assertIn("coverage.get('trade_gate')!='BLOCKED'",text)
        self.assertIn("coverage.get('historical_PIT_verified') is not False",text)
        self.assertIn("coverage.get('coverage_certified_for_trading') is not False",text)
        self.assertIn("raise ValueError('P2 coverage stale or unsafe for active P1 checkpoint')",text)
        self.assertIn("evidence/sources/current-p1-checkpoint.json",text)
    def test_research_only_event_guard_preserved(self):
        text=WORKFLOW.read_text()
        self.assertIn("github.event.workflow_run.conclusion == 'success'",text)
        self.assertIn("result['historical_PIT_verified'] is not False",text)
        self.assertIn("result['trade_gate']!='BLOCKED'",text)
        self.assertIn("assert pdf['certified_exchange_intervals']==0",text)

if __name__=="__main__":
    unittest.main()
