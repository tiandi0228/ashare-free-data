"""Offline P1 Git target preflight: no target commits, pushes or overwrites."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from collector.p1_private_git_commit_preflight import preflight, ARCHIVE
from collector.p1_offline_batch_staging import stage
from collector.p1_bounded_missing_shard_batch_plan import build
from tests.test_p1_bounded_missing_shard_batch_plan import BoundedBatchTests, COMMIT


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args],
                                   text=True).strip()


class PrivateGitPreflightTests(BoundedBatchTests):
    def setUp(self):
        super().setUp()
        self.repo = self.source.parent / "private-repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "P1 offline test")
        git(self.repo, "config", "user.email", "p1-test@example.invalid")
        self.archive = self.repo / ARCHIVE
        self.archive.mkdir(parents=True)
        (self.archive / "README.md").write_text("test archive root")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "baseline")
        self.gitsha = git(self.repo, "rev-parse", "HEAD")
        self.target = self.archive
        self.proposal = build(self.handoff, self.source, self.target,
                              COMMIT, self.gitsha, max_shards=1)
        self.scratch = self.source.parent / "scratch"
        stage(self.proposal, self.handoff, self.source, self.target,
              COMMIT, self.gitsha, self.scratch)

    def check(self, **kwargs):
        return preflight(kwargs.get("proposal", self.proposal),
                         self.handoff, self.source, self.repo,
                         kwargs.get("scratch", self.scratch),
                         COMMIT, kwargs.get("commit", self.gitsha))

    def test_clean_main_rechecks_staged_files_without_writing(self):
        result = self.check()
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["status"], "LOCAL_MAIN_CLEAN_SHA_STAGED_NO_WRITE_AUTHORIZED")
        self.assertIs(result["git_push_performed"], False)
        self.assertIs(result["writer_cutover_authorized"], False)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.gitsha)

    def test_new_target_commit_invalidates_proposal(self):
        with self.assertRaisesRegex(ValueError, "HEAD changed"):
            self.check(commit="a" * 40)

    def test_target_dirty_checkout_prevents_preflight(self):
        (self.archive / "scratch.txt").write_text("not clean")
        with self.assertRaisesRegex(ValueError, "must be clean"):
            self.check()

    def test_stage_tampering_prevents_preflight(self):
        path = self.scratch / "files" / self.proposal["selected_missing_files"][0]["path"]
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "staged bytes mismatch"):
            self.check()

    def test_target_branch_must_remain_main(self):
        git(self.repo, "checkout", "-qb", "unexpected")
        with self.assertRaisesRegex(ValueError, "on main"):
            self.check()

    def test_existing_destination_no_overwrite(self):
        path = self.archive / self.proposal["selected_missing_files"][0]["path"]
        path.parent.mkdir(parents=True)
        path.write_bytes(b"existing")
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main()
