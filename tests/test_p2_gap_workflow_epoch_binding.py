"""Regression: future P1 source epochs must never silently reuse an old P2 audit."""
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/p2-original-gap-window-triage.yml"

class ActiveGapEpochWorkflowTests(unittest.TestCase):
    def test_workflow_uses_active_validated_p1_roster(self):
        body = WORKFLOW.read_text()
        self.assertIn("from collector.p1_active_migration_checkpoint import resolve", body)
        self.assertIn("selected=resolve(Path('.'))", body)
        self.assertIn("epoch=selected['source_sha256']", body)
        self.assertIn("checkpoint_path=Path(selected['checkpoint_path'])", body)
        self.assertNotIn("epoch='5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022'", body)
        self.assertIn("witness=check_current_checkpoint(coverage,checkpoint,status)", body)
        self.assertIn("assert result['coverage_gaps_resolved']==0", body)
        self.assertIn("assert result['historical_PIT_verified'] is False", body)
        self.assertIn("assert result['trade_gate']=='BLOCKED'", body)

if __name__ == "__main__":
    unittest.main()
