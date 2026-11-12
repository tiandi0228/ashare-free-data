"""Manual gap archival push must re-verify on every retry, never after stale data."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector.p1_csv_archive import archive


class ManualGapArchiveRetryTests(unittest.TestCase):
    def exercise(self, guard, first_rejected=False):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/"receipt"
            folder.mkdir()
            csv=b"date,code,close\n2026-11-11,sh.600000,1.0\n"
            file=folder/"sh_600000.csv"
            file.write_bytes(csv)
            (folder/"quality.json").write_text('{"trade_gate":"BLOCKED"}\n')
            calls={"push":0,"guard":0}
            def recheck():
                calls["guard"]+=1
                return guard(calls["guard"])
            def fake_git(*args,cwd=None,check=True):
                command=args[0]
                if command=="clone":
                    Path(args[-1]).mkdir()
                if command=="ls-remote":
                    return SimpleNamespace(stdout="abc refs/heads/research-csv-archive",
                                           stderr="",returncode=0)
                if command=="diff":
                    return SimpleNamespace(stdout="",stderr="",returncode=1)
                if command=="push":
                    calls["push"]+=1
                    if first_rejected and calls["push"]==1:
                        return SimpleNamespace(stdout="",stderr="non-fast-forward",returncode=1)
                return SimpleNamespace(stdout="",stderr="",returncode=0)
            with patch("collector.p1_csv_archive.collect",
                       return_value=[(2,file,hashlib.sha256(csv).hexdigest())]):
                with patch("collector.p1_csv_archive.git",side_effect=fake_git):
                    archive({"source_sha256":"a"*64},
                            [(2,folder)],"owner/repo",pre_push_check=recheck)
            return calls

    def test_success_has_one_last_moment_recheck(self):
        c=self.exercise(lambda n: None)
        self.assertEqual(c,{"push":1,"guard":1})

    def test_retry_rechecks_again_before_second_push(self):
        c=self.exercise(lambda n: None,first_rejected=True)
        self.assertEqual(c,{"push":2,"guard":2})

    def test_stale_receipt_on_retry_halts_before_second_push(self):
        with self.assertRaisesRegex(ValueError,"checkpoint changed"):
            self.exercise(lambda n: (_ for _ in ()).throw(
                ValueError("checkpoint changed")) if n==2 else None,
                first_rejected=True)

    def test_first_recheck_failure_never_pushes(self):
        pushes=[]
        def bad_guard(n):
            pushes.append(n)
            raise ValueError("remote source epoch changed")
        with self.assertRaisesRegex(ValueError,"remote source epoch changed"):
            self.exercise(bad_guard)
        self.assertEqual(pushes,[1])


if __name__=="__main__":
    unittest.main()
