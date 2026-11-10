"""Disposable Git end-to-end batch drill: never writes to real remote."""
import subprocess
import unittest
from pathlib import Path

from collector.p1_disposable_git_transfer_drill import drill, MARKER
from tests.test_p1_private_remote_main_gate import RemoteMainGateTests, git
from tests.test_p1_bounded_missing_shard_batch_plan import COMMIT


class DisposableTransferDrillTests(unittest.TestCase):
    def setUp(self):
        fixture = RemoteMainGateTests("test_matching_remote_main_still_blocks_writes")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.marker = fixture.repo.parent / MARKER
        self.marker.write_text("P1_DISPOSABLE_TEST_ONLY\n")

    def run_drill(self):
        f = self.f
        return drill(f.proposal, f.handoff, f.source, f.repo, f.scratch,
                     COMMIT, f.gitsha)

    def test_nonforce_push_then_independent_clone_sha_readback(self):
        x = self.run_drill()
        self.assertEqual(x["status"], "DISPOSABLE_NONFORCE_PUSH_INDEPENDENT_SHA_MATCH")
        self.assertEqual(x["test_files"], 2)
        self.assertFalse(x["real_private_repo_modified"])
        self.assertFalse(x["writer_cutover_authorized"])
        self.assertEqual(x["trade_gate"], "BLOCKED")
        self.assertEqual(git(self.f.remote, "rev-parse", "refs/heads/main"),
                         x["new_test_commit"])

    def test_unauthorized_sandbox_rejected_before_writes(self):
        self.marker.unlink()
        with self.assertRaisesRegex(ValueError, "sandbox marker required"):
            self.run_drill()
        self.assertEqual(git(self.f.remote, "rev-parse", "refs/heads/main"),
                         self.f.gitsha)

    def test_remote_advanced_rejected_without_replay(self):
        f = self.f
        other = f.source.parent / "concurrent-clone"
        subprocess.run(["git", "clone", "-q", "-b", "main", str(f.remote),
                        str(other)], check=True)
        git(other, "config", "user.name", "test")
        git(other, "config", "user.email", "test@example.invalid")
        (other / "another.txt").write_text("advance")
        git(other, "add", "another.txt")
        git(other, "commit", "-qm", "advance remote")
        git(other, "push", "-q", "origin", "main")
        with self.assertRaisesRegex(ValueError, "remote main advanced"):
            self.run_drill()
        self.assertEqual(git(f.repo, "rev-parse", "HEAD"), f.gitsha)

    def test_repeat_batch_never_overwrites(self):
        first = self.run_drill()
        with self.assertRaises(ValueError):
            self.run_drill()
        self.assertEqual(git(self.f.remote, "rev-parse", "main"),
                         first["new_test_commit"])

    def test_staged_byte_change_rejected_before_commit(self):
        f = self.f
        rel = f.proposal["selected_missing_files"][0]["path"]
        (f.scratch / "files" / rel).write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "staged bytes mismatch"):
            self.run_drill()
        self.assertEqual(git(f.remote, "rev-parse", "main"), f.gitsha)


if __name__ == "__main__":
    unittest.main()
