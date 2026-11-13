"""Ensure manual P1 gap remote rechecks guard both sensitive boundaries."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / ".github/workflows/p1-fresh-vendor-roster.yml"

class GapRemoteWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = FLOW.read_text(encoding="utf-8")

    def test_two_remote_rechecks_bound_fetch_and_archive(self):
        s=self.text
        first=s.index("- name: Recheck live checkpoint and archive before manual gap vendor requests")
        fetch=s.index("- name: Fetch first real roster shard historical bars")
        second=s.index("- name: Recheck remote checkpoint and archive just before manual gap archival")
        archive=s.index("- name: Archive raw CSV to durable free Git research branch")
        self.assertLess(first,fetch)
        self.assertLess(fetch,second)
        self.assertLess(second,archive)
        self.assertEqual(s.count("python -m collector.p1_gap_remote_preflight"),2)

    def test_only_manual_explicit_gap_uses_readback(self):
        condition="if: github.event_name == 'workflow_dispatch' && env.P1_GAP_WINDOW != ''"
        steps=[section for section in self.text.split("      - name: ") if condition in section]
        self.assertEqual([section.splitlines()[0] for section in steps],[
            "Recheck live checkpoint and archive before manual gap vendor requests (NO WRITES)",
            "Recheck remote checkpoint and archive just before manual gap archival (NO WRITES)",
            "Verify remote checkpoint preserved the audited gap evidence",
        ])
        self.assertIn("test -s evidence/prior_ledger.json",self.text)
        self.assertIn("test -s evidence/p1_gap_remote_before_vendor.json",self.text)
        self.assertIn("evidence/p1_gap_remote_before_archive.json",self.text)

    def test_existing_schedule_and_durable_write_path_unchanged(self):
        s=self.text
        self.assertIn("  schedule:\n",s)
        self.assertIn("group: p1-fresh-mainboard-roster-serial",s)
        self.assertIn("python -m collector.p1_csv_archive",s)
        self.assertIn("python -m collector.p1_checkpoint --mode write",s)
        self.assertNotIn("--force",s)

    def test_no_order_unlock_and_no_global_task_gating(self):
        self.assertNotIn("trade_gate: OPEN",self.text)
        self.assertIn("id: pick",self.text)
        self.assertIn('GAP_ARGS=(--gap-window "$P1_GAP_WINDOW")',self.text)

if __name__ == "__main__":
    unittest.main()
