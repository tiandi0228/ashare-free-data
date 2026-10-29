import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_source_diagnostics import examine, summary_lines


class P1SourceDiagnosticTests(unittest.TestCase):
    def select(self, root, count=1):
        (root / "pilot_selection.json").write_text(json.dumps({
            "phase": "P1_BOUNDED_PILOT_SELECTION",
            "selected_count": count, "selected_shards": list(range(count)),
            "trade_gate": "BLOCKED"}))

    def quality(self, root, role, status, results, **extra):
        folder = root / role
        folder.mkdir(exist_ok=True)
        receipt = {
            "status": status, "trade_gate": "BLOCKED",
            "issuer_count": len(results), "query_attempts": len(results),
            "results": results, **extra,
        }
        (folder / "quality.json").write_text(json.dumps(receipt))

    def test_successful_first_and_not_requested_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 1)
            self.quality(root, "first_shard", "OBSERVED_SUBSET_UNVERIFIED", [
                {"code": "sh.600001", "status": "OBSERVED_UNVERIFIED"}])
            report = examine(root)
            self.assertEqual(report["roles"][0]["status"], "OBSERVED_UNVERIFIED")
            self.assertEqual(report["roles"][0]["observed_issuers"], 1)
            self.assertEqual(report["roles"][1]["status"], "NOT_REQUESTED")
            self.assertEqual(report["trade_gate"], "BLOCKED")
            self.assertEqual(report["orders"], [])

    def test_second_shard_failures_are_bounded_and_explained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 2)
            self.quality(root, "second_shard", "BLOCKED_PARTIAL", [
                {"code": "sh.600001", "status": "ERROR",
                 "failure_category": "PROVIDER_EMPTY_HISTORY"},
                {"code": "sh.600002", "status": "OBSERVED_UNVERIFIED"},
                {"code": "sh.600003", "status": "ERROR", "error_type": "TimeoutError"}])
            report = examine(root)
            second = report["roles"][1]
            self.assertEqual(second["status"], "SOURCE_INCOMPLETE")
            self.assertEqual(second["failed_issuers"], 2)
            self.assertEqual(second["observed_issuers"], 1)
            self.assertEqual(second["failure_categories"],
                             ["PROVIDER_EMPTY_HISTORY", "TimeoutError"])
            summary = "\n".join(summary_lines(report))
            self.assertIn("sh.600001", summary)
            self.assertIn("PROVIDER_EMPTY_HISTORY", summary)
            self.assertIn("trading", summary)

    def test_timeout_preserved_even_when_partial_receipt_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 2)
            self.quality(root, "second_shard", "BLOCKED_PARTIAL", [
                {"code": "sh.600001", "status": "ERROR",
                 "error_type": "TimeoutError"}])
            folder = root / "second_shard"
            (folder / "runner_timeout.json").write_text(json.dumps({
                "phase": "P1_RUNNER_TIMEOUT",
                "exit_code": 124, "trade_gate": "BLOCKED"}))
            second = examine(root)["roles"][1]
            self.assertEqual(second["status"], "RUNNER_TIMEOUT")
            self.assertEqual(second["runner_timeout_exit_code"], 124)
            self.assertEqual(second["failed_issuers"], 1)

    def test_missing_bad_and_unsafe_receipts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 1)
            self.assertEqual(examine(root)["roles"][0]["status"], "NOT_PRODUCED")
            folder = root / "first_shard"
            folder.mkdir()
            (folder / "quality.json").write_text("not json")
            self.assertEqual(examine(root)["roles"][0]["status"],
                             "INVALID_SOURCE_RECEIPT")
            (folder / "quality.json").write_text(json.dumps({
                "trade_gate": "OPEN", "status": "OBSERVED_SUBSET_UNVERIFIED",
                "results": []}))
            self.assertEqual(examine(root)["roles"][0]["status"],
                             "UNSAFE_SOURCE_RECEIPT")

    def test_second_csv_replay_rejection_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 2)
            # The provider says the query completed, but independent replay
            # rejected this source as inconsistent.
            self.quality(root, "second_shard", "OBSERVED_SUBSET_UNVERIFIED", [
                {"code": "sh.600001", "status": "OBSERVED_UNVERIFIED"}])
            (root / "optional_second.json").write_text(json.dumps({
                "phase": "P1_OPTIONAL_SECOND_SHARD_POLICY",
                "requested_second": True, "accepted_second": False,
                "status": "SECOND_INVALID_PRESERVE_FIRST",
                "second_rejection_type": "ValueError",
                "historical_PIT_verified": False, "trade_gate": "BLOCKED",
                "orders": [], "executable_candidates": [],
            }))
            second = examine(root)["roles"][1]
            self.assertEqual(second["observed_issuers"], 1)
            self.assertEqual(second["status"], "SECOND_REJECTED_PRESERVE_FIRST")
            self.assertIn("INDEPENDENT_REPLAY_ValueError",
                          second["failure_categories"])
            self.assertEqual(second["optional_second_policy_status"],
                             "SECOND_INVALID_PRESERVE_FIRST")

    def test_verified_second_distinguishes_provider_from_replay_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 2)
            self.quality(root, "second_shard", "OBSERVED_SUBSET_UNVERIFIED", [
                {"code": "sh.600001", "status": "OBSERVED_UNVERIFIED"}])
            (root / "optional_second.json").write_text(json.dumps({
                "phase": "P1_OPTIONAL_SECOND_SHARD_POLICY",
                "requested_second": True, "accepted_second": True,
                "second_verification_passed": True,
                "status": "SECOND_SHARD_VERIFIED",
                "historical_PIT_verified": False, "trade_gate": "BLOCKED",
                "orders": [], "executable_candidates": [],
            }))
            self.assertEqual(examine(root)["roles"][1]["status"],
                             "SECOND_INDEPENDENTLY_VERIFIED_UNVERIFIED")

    def test_unsafe_optional_second_policy_cannot_hide_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 2)
            self.quality(root, "second_shard", "OBSERVED_SUBSET_UNVERIFIED", [
                {"code": "sh.600001", "status": "OBSERVED_UNVERIFIED"}])
            policy = root / "optional_second.json"
            policy.write_text(json.dumps({
                "phase": "P1_OPTIONAL_SECOND_SHARD_POLICY",
                "requested_second": True, "accepted_second": True,
                "second_verification_passed": True,
                "status": "SECOND_SHARD_VERIFIED",
                "trade_gate": "OPEN",
                "historical_PIT_verified": False,
                "orders": [], "executable_candidates": [],
            }))
            self.assertEqual(examine(root)["roles"][1]["status"],
                             "INVALID_OPTIONAL_SECOND_POLICY")
            policy.write_text("malformed")
            self.assertEqual(examine(root)["roles"][1]["status"],
                             "INVALID_OPTIONAL_SECOND_POLICY")

    def test_second_verdict_cannot_override_missing_source_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.select(root, 2)
            (root / "optional_second.json").write_text(json.dumps({
                "phase": "P1_OPTIONAL_SECOND_SHARD_POLICY",
                "requested_second": True, "accepted_second": True,
                "second_verification_passed": True,
                "status": "SECOND_SHARD_VERIFIED",
                "trade_gate": "BLOCKED",
                "historical_PIT_verified": False,
                "orders": [], "executable_candidates": [],
            }))
            self.assertEqual(examine(root)["roles"][1]["status"],
                             "SECOND_POLICY_SOURCE_CONFLICT")

    def test_actions_preserves_diagnostics_after_failed_acquisition(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        marker = "      - name: Preserve per-shard Baostock source errors and timeouts"
        self.assertEqual(workflow.count(marker), 1)
        section = workflow.split(marker, 1)[1].split(
            "      - name: Publish P1 run diagnostics (research only)", 1)[0]
        self.assertIn("if: always()", section)
        self.assertIn("python -m collector.p1_source_diagnostics", section)
        self.assertIn("evidence/source_diagnostics.json", section)
        self.assertIn("evidence/optional_second.json", workflow)

    def test_archive_progress_is_not_invented(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(examine(root)["archival_progress_status"], "UNAVAILABLE")
            (root / "p1_run_progress.json").write_text(json.dumps({
                "trade_gate": "BLOCKED", "status": "DURABLE_PROGRESS"}))
            self.assertEqual(examine(root)["archival_progress_status"], "DURABLE_PROGRESS")
            (root / "p1_run_progress.json").write_text(json.dumps({
                "trade_gate": "OPEN", "status": "DURABLE_PROGRESS"}))
            self.assertEqual(examine(root)["archival_progress_status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
