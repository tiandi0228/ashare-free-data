"""Safe retry after possible push: test only disposable bare remote."""
import subprocess
import unittest

from collector.p1_private_archive_retry_decision import decide
from tests.test_p1_private_remote_main_gate import RemoteMainGateTests, git
from tests.test_p1_independent_postpush_readback import PostPushReadbackTests


class RetryDecisionTests(unittest.TestCase):
    def use_fixture(self, klass, method):
        fixture = klass(method)
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_remote_unchanged_is_not_automatic_retry_authorization(self):
        f = self.use_fixture(RemoteMainGateTests, "test_matching_remote_main_still_blocks_writes")
        clone = f.source.parent / "retry-clone"
        subprocess.check_call(["git", "clone", "-q", "-b", "main",
                               str(f.remote), str(clone)])
        result = decide(f.proposal, f.handoff, clone, f.gitsha)
        self.assertEqual(result["status"], "REMOTE_UNCHANGED_REPLAN_BEFORE_ANY_WRITE")
        self.assertFalse(result["independent_batch_readback_passed"])
        self.assertFalse(result["automatic_copy_authorized"])
        self.assertFalse(result["git_push_performed"])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_exact_already_pushed_batch_is_independently_verified_and_not_replayed(self):
        f = self.use_fixture(PostPushReadbackTests, "test_independent_clone_verifies_only_selected_added_files")
        result = decide(f.proposal, f.handoff, f.auditor, f.gitsha, f.newsha)
        self.assertEqual(result["status"], "REMOTE_HAS_EXACT_SHA_BATCH_ALREADY_NO_REPLAY")
        self.assertTrue(result["independent_batch_readback_passed"])
        self.assertTrue(result["do_not_replay_existing_batch"])
        self.assertFalse(result["git_push_performed"])
        self.assertFalse(result["writer_cutover_authorized"])

    def test_unknown_remote_change_is_never_auto_retried(self):
        f = self.use_fixture(PostPushReadbackTests, "test_independent_clone_verifies_only_selected_added_files")
        with self.assertRaisesRegex(ValueError, "unrecognized remote main change"):
            decide(f.proposal, f.handoff, f.auditor, f.gitsha)

    def test_wrong_new_sha_and_dirty_checkout_are_rejected(self):
        f = self.use_fixture(PostPushReadbackTests, "test_independent_clone_verifies_only_selected_added_files")
        with self.assertRaisesRegex(ValueError, "unrecognized remote main change"):
            decide(f.proposal, f.handoff, f.auditor, f.gitsha, "c" * 40)
        (f.auditor / "UNTRACKED").write_text("dirty")
        with self.assertRaisesRegex(ValueError, "dirty"):
            decide(f.proposal, f.handoff, f.auditor, f.gitsha, f.newsha)

    def test_remote_drift_after_checkout_blocks_retry(self):
        f = self.use_fixture(RemoteMainGateTests, "test_matching_remote_main_still_blocks_writes")
        clone = f.source.parent / "retry-clone"
        subprocess.check_call(["git", "clone", "-q", "-b", "main",
                               str(f.remote), str(clone)])
        (f.repo / "change.txt").write_text("remote drift")
        git(f.repo, "add", "change.txt")
        git(f.repo, "commit", "-qm", "concurrent update")
        git(f.repo, "push", "-q", "origin", "main")
        with self.assertRaisesRegex(ValueError, "does not match remote main"):
            decide(f.proposal, f.handoff, clone, f.gitsha)


if __name__ == "__main__":
    unittest.main()
