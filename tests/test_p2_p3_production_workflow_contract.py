"""Contract tests for production P2 -> P3 source wiring; no Actions dispatch.

These only validate workflow configuration. Real artifact availability and epoch
provenance remain independent runtime gates.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PRODUCER = "P2 original CSV 21-bar gap root-cause audit (NO TRADES)"
P3_PRODUCER = "P3 rotating official originals for full audited P1 issuer queue (NO TRADES)"


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def block(source, start, end):
    """Extract a job or permissions region at its own YAML indentation."""
    a = source.index(start)
    tail = source[a + len(start):]
    if start == "  replay_once:":
        next_job = re.search(r"(?m)^  [a-zA-Z_][\\w-]*:", tail)
        return source[a:a + len(start) + next_job.start()] if next_job else source[a:]
    b = source.find(end, a + len(start))
    return source[a:] if b == -1 else source[a:b]


class ProductionArtifactWiringTests(unittest.TestCase):
    def test_p2_producer_main_push_and_completion_trigger(self):
        producer = workflow("p2-original-gap-window-triage.yml")
        self.assertIn("name: " + PRODUCER, producer)
        self.assertIn("push:\n    branches: [main]", producer)
        self.assertIn("'collector/p2_original_gap_window_triage.py'", producer)
        replay = block(producer, "  replay_once:", "\n  ")
        self.assertIn("github.event_name == 'push'", replay)
        self.assertIn("refs/heads/main", replay)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", replay)
        self.assertIn("needs: offline", replay)
        self.assertIn("check_current_checkpoint", replay)
        self.assertIn("--archive-epoch", replay)
        self.assertIn("--coverage", replay)
        self.assertIn("p2-original-gap-triage-${{ github.run_id }}", replay)
        self.assertIn("evidence/p2-original-gap-triage.json", replay)

    def test_crosswalk_requires_both_producers_and_real_source_selector(self):
        crosswalk = workflow("p2-p3-original-gap-crosswalk.yml")
        self.assertIn(PRODUCER, crosswalk)
        self.assertIn(P3_PRODUCER, crosswalk)
        self.assertIn("push:\n    branches: [main]", crosswalk)
        self.assertIn("collector.p2_p3_artifact_source_select", crosswalk)
        replay = block(crosswalk, "  replay_once:", "\n  ")
        self.assertIn("needs: offline", replay)
        self.assertIn("github.event_name == 'push'", replay)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", replay)
        self.assertIn("gh run download", replay)
        self.assertIn("p2-original-gap-triage-$P2_RUN", replay)
        self.assertIn("p3-full-p1-official-scout-$P3_RUN", replay)
        self.assertIn("collector.p2_p3_current_source_guard", replay)
        self.assertIn("collector.p2_p3_gap_crosswalk", replay)
        self.assertIn("historical_PIT_verified", replay)
        self.assertIn("trade_gate", replay)

    def test_selector_must_reject_successful_empty_or_expired_runs(self):
        source = (ROOT / "collector" / "p2_p3_artifact_source_select.py").read_text()
        self.assertIn('"p2-original-gap-triage-"', source)
        self.assertIn('"p3-full-p1-official-scout-"', source)
        self.assertIn('row.get("event") in ALLOWED_SOURCE_EVENTS', source)
        self.assertIn('"push", "workflow_run", "workflow_dispatch"', source)
        self.assertIn('a.get("expired") is False', source)
        self.assertIn('a["size_in_bytes"] > 0', source)
        self.assertIn("no successful non-expired evidence artifact found", source)
        self.assertIn('trade_gate="BLOCKED"', source)

    def test_no_prod_workflow_grants_write_or_trading_permissions(self):
        for name in ("p2-original-gap-window-triage.yml",
                     "p2-p3-original-gap-crosswalk.yml"):
            with self.subTest(name=name):
                src = workflow(name)
                permissions = block(src, "permissions:", "\njobs:")
                self.assertIn("contents: read", permissions)
                self.assertIn("actions: read", permissions)
                self.assertNotIn("write", permissions)
                self.assertNotIn("pull-requests: write", permissions)


if __name__ == "__main__":
    unittest.main()
