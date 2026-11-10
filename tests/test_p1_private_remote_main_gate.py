"""Disposable bare Git remote tests; never accesses actual private repo."""
import subprocess
import unittest
from collector.p1_private_remote_main_gate import gate
from tests.test_p1_private_git_commit_preflight import PrivateGitPreflightTests, git
from tests.test_p1_bounded_missing_shard_batch_plan import COMMIT

class RemoteMainGateTests(PrivateGitPreflightTests):
    def setUp(self):
        super().setUp()
        self.remote = self.source.parent / "remote.git"
        subprocess.check_call(["git","init","-q","--bare",str(self.remote)])
        git(self.repo,"remote","add","origin",str(self.remote))
        git(self.repo,"push","-q","origin","main")

    def remote_gate(self):
        return gate(self.proposal,self.handoff,self.source,self.repo,
                    self.scratch,COMMIT,self.gitsha)

    def test_matching_remote_main_still_blocks_writes(self):
        x=self.remote_gate()
        self.assertEqual(x["observed_remote_commit"],self.gitsha)
        self.assertFalse(x["remote_check_atomic_with_future_push"])
        self.assertFalse(x["git_push_performed"])
        self.assertFalse(x["writer_cutover_authorized"])
        self.assertEqual(x["trade_gate"],"BLOCKED")

    def test_remote_advance_rejects_stale_batch(self):
        other=self.source.parent/"concurrent-clone"
        subprocess.check_call(["git","clone","-q","-b","main",str(self.remote),str(other)])
        git(other,"config","user.name","audit")
        git(other,"config","user.email","audit@example.invalid")
        (other/"another.txt").write_text("new")
        git(other,"add",".")
        git(other,"commit","-qm","remote advanced")
        git(other,"push","-q","origin","main")
        with self.assertRaisesRegex(ValueError,"remote main advanced"):
            self.remote_gate()
        self.assertEqual(git(self.repo,"rev-parse","HEAD"),self.gitsha)

    def test_no_remote_is_failure(self):
        git(self.repo,"remote","remove","origin")
        with self.assertRaises(subprocess.CalledProcessError):
            self.remote_gate()

if __name__=="__main__":
    unittest.main()
