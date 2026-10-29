import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_csv_archive import collect

class CSVArchiveTests(unittest.TestCase):
    def test_non_mainboard_issuer_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sz.300001","status":"OBSERVED_UNVERIFIED",
                                 "sha256":"b"*64}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"invalid or duplicate issuer"):
                collect({"shards":[{"sha256":"a"*64,"count":1}]},[(0,path)])

    def test_archive_uses_shallow_git_history_for_bounded_cloud_runtime(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from collector.p1_csv_archive import archive, BRANCH
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/"receipt"
            folder.mkdir()
            (folder/"quality.json").write_text('{"trade_gate":"BLOCKED"}')
            plan={"source_sha256":"a"*64}
            def simulated_git(*args,**kwargs):
                if args[0]=="ls-remote":
                    return SimpleNamespace(stdout="abc refs/heads/"+BRANCH,returncode=0)
                return SimpleNamespace(stdout="",returncode=0)
            with patch("collector.p1_csv_archive.collect",return_value=[]):
                with patch("collector.p1_csv_archive.git",side_effect=simulated_git) as git:
                    archive(plan,[(0,folder)],"user/repo")
            commands=[call.args for call in git.call_args_list]
            clones=[args for args in commands if args[0]=="clone"]
            fetches=[args for args in commands if args[0]=="fetch"]
            self.assertEqual(len(clones),1)
            self.assertIn("--depth=1",clones[0])
            self.assertIn("--no-checkout",clones[0])
            self.assertEqual(len(fetches),1)
            self.assertEqual(fetches[0][:4],("fetch","--depth=1","origin",BRANCH))

    def test_git_operations_have_bounded_timeout(self):
        import subprocess
        from unittest.mock import patch
        from collector.p1_csv_archive import git
        with patch("collector.p1_csv_archive.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(["git","fetch"],90)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                git("fetch","origin","research-csv-archive")
            self.assertEqual(run.call_args.kwargs["timeout"],90)

    def test_verified_csv_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            plan={"shards":[{"sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"count":1}]}
            receipt={"manifest_sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"issuer_count":1,"status":"OBSERVED_SUBSET_UNVERIFIED",
                     "trade_gate":"BLOCKED","results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            result=collect(plan,[(0,path)])
            self.assertEqual(len(result),1)
            (path/"sh_600000.csv").write_text("tampered")
            with self.assertRaises(ValueError):collect(plan,[(0,path)])
    def test_wrong_shard_membership_rejected_before_git_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED",
                                 "sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"membership"):
                collect({"shards":[{"sha256":"a"*64,"count":1}]},[(0,path)])

    def test_duplicate_issuer_rejected_before_archive_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            item={"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}
            plan={"shards":[{"sha256":"a"*64,"count":2}]}
            receipt={"manifest_sha256":"a"*64,"issuer_count":2,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[item,item]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"duplicate issuer"):
                collect(plan,[(0,path)])

    def test_duplicate_shard_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            plan={"shards":[{"sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"count":1}]}
            receipt={"manifest_sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"duplicate archive shard"):
                collect(plan,[(0,path),(0,path)])

    def test_failed_issuer_result_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\\n2026-01-01,1.2\\n"
            (path/"sh_600000.csv").write_bytes(raw)
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000","status":"ERROR",
                                 "sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"result status"):
                collect({"shards":[{"sha256":"a"*64,"count":1}]},[(0,path)])

    def test_missing_issuer_status_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\\n2026-01-01,1.2\\n"
            (path/"sh_600000.csv").write_bytes(raw)
            plan={"shards":[{"sha256":"a"*64,"count":1}]}
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000",
                                 "sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"result status"):
                collect(plan,[(0,path)])

    def test_blocked_gate_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            plan={"shards":[{"sha256":"a"*64,"count":0}]}
            (path/"quality.json").write_text(json.dumps({"manifest_sha256":"a"*64,"issuer_count":0,"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"OPEN","results":[]}))
            with self.assertRaises(ValueError):collect(plan,[(0,path)])
if __name__=="__main__":unittest.main()
