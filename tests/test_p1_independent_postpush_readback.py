"""Disposable bare-remote P1 Git push simulation; verifier is read-only."""
import subprocess
import unittest
from pathlib import Path

from collector.p1_independent_postpush_readback import verify
from collector.p1_private_git_commit_preflight import ARCHIVE
from tests.test_p1_private_remote_main_gate import RemoteMainGateTests, git


class PostPushReadbackTests(RemoteMainGateTests):
    def setUp(self):
        super().setUp()
        self.sender = self.repo
        self.auditor = self.source.parent / "independent-clone"
        for row in self.proposal["selected_missing_files"]:
            original = self.scratch / "files" / row["path"]
            destination = self.sender / ARCHIVE / row["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(original.read_bytes())
        git(self.sender, "add", "--", str(ARCHIVE))
        git(self.sender, "commit", "-qm", "synthetic P1 selected batch")
        git(self.sender, "push", "-q", "origin", "main")
        self.newsha = git(self.sender, "rev-parse", "HEAD")
        subprocess.check_call([
            "git", "clone", "-q", "-b", "main", str(self.remote),
            str(self.auditor)])

    def readback(self, **changes):
        return verify(changes.get("proposal", self.proposal), self.handoff,
                      self.auditor, changes.get("old", self.gitsha),
                      changes.get("new", self.newsha))

    def test_independent_clone_verifies_only_selected_added_files(self):
        result = self.readback()
        self.assertEqual(result["added_file_count"], self.proposal["selected_file_count"])
        self.assertTrue(result["commit_scoped_selected_bytes_verified"])
        self.assertFalse(result["whole_destination_mirror_certified"])
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(git(self.auditor, "status", "--porcelain"), "")

    def test_unexpected_commit_change_rejected(self):
        # A second synthetic commit that alters an unrelated tracked file
        # must never satisfy an unchanged proposed batch.
        (self.auditor / "README.md").write_text("changed")
        git(self.auditor, "add", "README.md")
        git(self.auditor, "config", "user.name", "audit")
        git(self.auditor, "config", "user.email", "audit@example.invalid")
        git(self.auditor, "commit", "-qm", "unexpected")
        with self.assertRaises(ValueError):
            self.readback(new=git(self.auditor, "rev-parse", "HEAD"))

    def test_wrong_base_and_wrong_commit_refused(self):
        with self.assertRaises(ValueError):
            self.readback(old="a" * 40)
        with self.assertRaises(ValueError):
            self.readback(new="b" * 40)

    def test_dirty_independent_checkout_rejected(self):
        (self.auditor / "rogue.txt").write_text("untracked")
        with self.assertRaisesRegex(ValueError, "local modifications"):
            self.readback()

    def test_tampered_selected_file_rejected(self):
        rel=self.proposal["selected_missing_files"][0]["path"]
        (self.auditor / ARCHIVE / rel).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "local modifications"):
            self.readback()


if __name__ == "__main__":
    unittest.main()
