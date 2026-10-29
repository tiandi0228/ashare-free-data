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
