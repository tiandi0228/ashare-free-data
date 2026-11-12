"""Ensure only explicit manual dispatch controls focused P1 selection."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/p1-fresh-vendor-roster.yml"


class ManualOnlyGapIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=WORKFLOW.read_text()

    def test_gap_control_is_optional_manual_dispatch(self):
        s=self.source
        self.assertIn('      gap_window:\n',s)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.gap_window || ''",s)
        self.assertIn('[[ "${GITHUB_EVENT_NAME}" == "workflow_dispatch" ]]',s)
        self.assertIn('GAP_ARGS=(--gap-window "$P1_GAP_WINDOW")',s)
        self.assertIn('"${GAP_ARGS[@]}" --per-run "$P1_REQUESTED_SHARDS"',s)

    def test_scheduled_trigger_still_exists_and_is_not_conditional(self):
        s=self.source
        self.assertIn("  schedule:\n",s)
        self.assertIn("    - cron: '10 0 * * 1-5'",s)
        self.assertIn("    - cron: '10 15 * * 6,0'",s)
        self.assertIn("concurrency:\n  group: p1-fresh-mainboard-roster-serial",s)

    def test_provenance_and_archival_checks_remain(self):
        s=self.source
        self.assertIn("Recover durable same-version GitHub checkpoint",s)
        self.assertIn("Recover previously archived but uncheckpointed research shards",s)
        self.assertIn("Record bounded pilot selection for audit",s)
        self.assertIn('requested=int(os.environ["P1_REQUESTED_SHARDS"])',s)

    def test_no_auto_launch_or_unlock(self):
        s=self.source
        self.assertNotIn("trade_gate: OPEN",s)
        self.assertIn("P1_GAP_WINDOW:",s)
        self.assertIn("      - name: Offline source tests",s)


if __name__=="__main__":
    unittest.main()
