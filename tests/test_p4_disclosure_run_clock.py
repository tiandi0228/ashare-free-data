from copy import deepcopy
import unittest

from collector.p4_disclosure_run_clock import verify


class DisclosureRunClockTests(unittest.TestCase):
    def setUp(self):
        self.head = "a" * 40
        self.repo = "owner/repo"
        self.run = dict(id=42, run_attempt=2, head_sha=self.head, head_branch="main",
                        path=".github/workflows/p3-prospective-official-observation.yml",
                        status="completed", conclusion="success", repository={"full_name": self.repo},
                        run_started_at="2026-12-01T07:35:00Z", updated_at="2026-12-01T07:50:00Z")
        self.artifact = dict(id=99, name="p4-registered-disclosure-42-2", expired=False,
                             created_at="2026-12-01T07:48:00Z",
                             workflow_run=dict(id=42, head_sha=self.head, head_branch="main"))
        self.record = dict(observed_at="2026-12-01T15:47:00+08:00")

    def check(self):
        return verify(self.run, self.artifact, self.record, repo=self.repo,
                      run_id=42, attempt=2, head_sha=self.head)

    def test_consistent_attempt_and_receipt_clocks(self):
        out = self.check()
        self.assertEqual(out["run_attempt"], 2)
        self.assertEqual(out["observed_at"], "2026-12-01T07:47:00+00:00")

    def test_old_attempt_or_unrelated_artifact_rejected(self):
        for mutation in (dict(name="p4-registered-disclosure-42-1"), dict(expired=True),
                         dict(workflow_run=dict(id=43, head_sha=self.head, head_branch="main"))):
            original = deepcopy(self.artifact)
            self.artifact.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "not bound"):
                self.check()
            self.artifact = original

    def test_backdated_or_future_observation_rejected(self):
        for stamp in ("2026-12-01T15:34:59+08:00", "2026-12-01T15:48:01+08:00",
                      "2026-12-01T15:47:00", "2026-12-02T07:40:00Z"):
            self.record["observed_at"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                self.check()

    def test_wrong_run_or_active_attempt_rejected(self):
        for changes in (dict(run_attempt=1), dict(status="in_progress"), dict(head_branch="topic")):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "run attempt"):
                verify({**self.run, **changes}, self.artifact, self.record, repo=self.repo,
                       run_id=42, attempt=2, head_sha=self.head)
