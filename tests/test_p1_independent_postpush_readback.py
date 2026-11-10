"""Disposable bare-remote P1 Git push simulation; verifier is read-only."""
import subprocess
import unittest
from pathlib import Path

from collector.p1_independent_postpush_readback import verify
from collector.p1_private_git_commit_preflight import ARCHIVE
from tests.test_p1_private_remote_main_gate import RemoteMainGateTests, git


class PostPushReadbackTests(unittest.TestCase):
    def setUp(self):
        # Reuse only the disposable fixture setup, not its inherited test suite:
        # those pre-push expectations do not hold after synthetic push.
        fixture = RemoteMainGateTests("test_matching_remote_main_still_blocks_writes")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for key in ("source", "target", "repo", "remote", "scratch",
                    "handoff", "proposal", "gitsha"):
            setattr(self, key, getattr(fixture, key))
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

    def test_unselected_allowlisted_original_in_same_commit_is_rejected(self):
        # Build a different synthetic child of the original base, containing
        # this batch PLUS one otherwise valid handoff file from another shard.
        git(self.sender, "checkout", "-qb", "extra-original", self.gitsha)
        for row in self.proposal["selected_missing_files"]:
            destination = self.sender / ARCHIVE / row["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.source / row["path"]).read_bytes())
        selected = {row["path"] for row in self.proposal["selected_missing_files"]}
        extra = next(row["path"] for row in self.handoff["original_paths_and_sha256"]
                     if row["path"] not in selected)
        extra_path = self.sender / ARCHIVE / extra
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_bytes((self.source / extra).read_bytes())
        git(self.sender, "add", "--", str(ARCHIVE))
        git(self.sender, "commit", "-qm", "synthetic unexpected extra original")
        unexpected_sha = git(self.sender, "rev-parse", "HEAD")
        # Make the synthetic object available on the disposable bare remote,
        # then atomically replace its test main ref using expected-old SHA.
        git(self.sender, "push", "-q", "origin", "extra-original:refs/heads/test-extra")
        git(self.remote, "update-ref", "refs/heads/main", unexpected_sha, self.newsha)
        git(self.auditor, "fetch", "-q", "origin", "main")
        git(self.auditor, "reset", "--hard", unexpected_sha)
        with self.assertRaisesRegex(ValueError, "commit additions differ"):
            self.readback(new=unexpected_sha)

    def test_mutated_frozen_selected_digest_rejected(self):
        import copy
        proposal = copy.deepcopy(self.proposal)
        proposal["selected_inventory_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "selected inventory SHA mismatch"):
            self.readback(proposal=proposal)

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
