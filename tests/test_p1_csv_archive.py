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

    def test_retry_rebases_on_latest_p1_and_p4_evidence_without_overwriting(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from collector.p1_csv_archive import archive, BRANCH
        pushes=[];clones=[]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"fresh"
            source.mkdir()
            (source/"quality.json").write_text('{"trade_gate":"BLOCKED"}')
            original=b"date,code,close\\n2026-10-20,sh.600000,10\\n"
            (source/"sh_600000.csv").write_bytes(original)
            wanted=(1,source/"sh_600000.csv",hashlib.sha256(original).hexdigest())
            def fake_git(*args,cwd=None,check=True):
                cmd=args[0]
                if cmd=="clone":
                    work=Path(args[-1]);work.mkdir()
                    clones.append(work)
                if cmd=="ls-remote":
                    return SimpleNamespace(stdout="abc refs/heads/"+BRANCH,stderr="",returncode=0)
                if cmd=="checkout":
                    work=Path(cwd)
                    epoch=work/("a"*16)
                    epoch.mkdir()
                    count=[9] if len(clones)==1 else [9,10]
                    (epoch/"archive_status.json").write_text(json.dumps({
                        "source_sha256":"a"*64,"trade_gate":"BLOCKED",
                        "archived_shards":count}))
                    old=epoch/"shard_0009"
                    old.mkdir()
                    (old/"quality.json").write_text("unaltered-old-source")
                    p4=work/"p4-current-tail"/"run_sample"
                    p4.mkdir(parents=True)
                    (p4/"original.json").write_text(
                        "p4_before" if len(clones)==1 else "p4_concurrent")
                if cmd=="diff":
                    return SimpleNamespace(stdout="",stderr="",returncode=1)
                if cmd=="push":
                    work=Path(cwd)
                    snapshot={
                        "work":str(work),
                        "marker":json.loads((work/("a"*16)/"archive_status.json").read_text()),
                        "prior":(work/("a"*16)/"shard_0009"/"quality.json").read_text(),
                        "p4":(work/"p4-current-tail"/"run_sample"/"original.json").read_text(),
                    }
                    pushes.append(snapshot)
                    if len(pushes)==1:
                        return SimpleNamespace(stdout="",stderr="[rejected] (fetch first)",returncode=1)
                return SimpleNamespace(stdout="",stderr="",returncode=0)
            with patch("collector.p1_csv_archive.collect",return_value=[wanted]):
                with patch("collector.p1_csv_archive.git",side_effect=fake_git) as mocked:
                    archive({"source_sha256":"a"*64},[(1,source)],"owner/repo")
            self.assertEqual(len(clones),2)
            self.assertEqual(len(pushes),2)
            self.assertNotEqual(clones[0],clones[1])
            accepted=pushes[-1]
            self.assertEqual(accepted["marker"]["archived_shards"],[1,9,10])
            self.assertEqual(accepted["prior"],"unaltered-old-source")
            self.assertEqual(accepted["p4"],"p4_concurrent")
            push_calls=[c for c in mocked.call_args_list if c.args[0]=="push"]
            self.assertEqual(len(push_calls),2)
            self.assertTrue(all(c.kwargs.get("check") is False for c in push_calls))
            self.assertFalse(any("force" in str(c.args) for c in push_calls))

    def test_concurrent_retries_are_capped_at_three_and_fail_closed(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from collector.p1_csv_archive import archive
        calls={"clone":0,"push":0}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"fresh";source.mkdir()
            (source/"quality.json").write_text('{"trade_gate":"BLOCKED"}')
            def fake_git(*args,cwd=None,check=True):
                if args[0]=="clone":
                    calls["clone"]+=1
                    Path(args[-1]).mkdir()
                if args[0]=="diff":
                    return SimpleNamespace(stdout="",stderr="",returncode=1)
                if args[0]=="push":
                    calls["push"]+=1
                    return SimpleNamespace(stdout="",stderr="[rejected] (non-fast-forward)",returncode=1)
                return SimpleNamespace(stdout="",stderr="",returncode=0)
            with patch("collector.p1_csv_archive.collect",return_value=[]):
                with patch("collector.p1_csv_archive.git",side_effect=fake_git):
                    with self.assertRaisesRegex(ValueError,"exhausted bounded retries"):
                        archive({"source_sha256":"a"*64},[(1,source)],"owner/repo")
            self.assertEqual(calls,{"clone":3,"push":3})

    def test_auth_failure_never_masquerades_as_concurrent_retry(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from collector.p1_csv_archive import archive
        counts={"clone":0,"push":0}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"fresh";source.mkdir()
            (source/"quality.json").write_text('{"trade_gate":"BLOCKED"}')
            def fake_git(*args,cwd=None,check=True):
                if args[0]=="clone":
                    counts["clone"]+=1;Path(args[-1]).mkdir()
                if args[0]=="diff":
                    return SimpleNamespace(stdout="",stderr="",returncode=1)
                if args[0]=="push":
                    counts["push"]+=1
                    return SimpleNamespace(stdout="",stderr="403 Permission denied",returncode=128)
                return SimpleNamespace(stdout="",stderr="",returncode=0)
            with patch("collector.p1_csv_archive.collect",return_value=[]):
                with patch("collector.p1_csv_archive.git",side_effect=fake_git):
                    with self.assertRaisesRegex(ValueError,"not retryable"):
                        archive({"source_sha256":"a"*64},[(1,source)],"owner/repo")
            self.assertEqual(counts,{"clone":1,"push":1})

    def test_existing_different_receipt_rejected_before_remote_push(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from collector.p1_csv_archive import archive
        cmds=[]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"fresh";source.mkdir()
            (source/"quality.json").write_text("fresh original")
            def fake_git(*args,cwd=None,check=True):
                cmds.append(args[0])
                if args[0]=="clone":Path(args[-1]).mkdir()
                if args[0]=="ls-remote":
                    return SimpleNamespace(stdout="abc refs/heads/research-csv-archive",
                                           stderr="",returncode=0)
                if args[0]=="checkout":
                    d=Path(cwd)/("a"*16)/"shard_0001"
                    d.mkdir(parents=True)
                    (d/"quality.json").write_text("different immutable original")
                return SimpleNamespace(stdout="",stderr="",returncode=0)
            with patch("collector.p1_csv_archive.collect",return_value=[]):
                with patch("collector.p1_csv_archive.git",side_effect=fake_git):
                    with self.assertRaisesRegex(ValueError,"refuse to overwrite archived receipt"):
                        archive({"source_sha256":"a"*64},[(1,source)],"owner/repo")
        self.assertNotIn("push",cmds)

    def test_explicit_git_concurrency_is_only_retryable_failure(self):
        from types import SimpleNamespace
        from collector.p1_csv_archive import is_concurrent_push_rejection
        for text in ("[rejected] (non-fast-forward)","[rejected] (fetch first)","stale info"):
            self.assertTrue(is_concurrent_push_rejection(
                SimpleNamespace(returncode=1,stderr=text,stdout="")))
        for text in ("403 forbidden","authentication failed","connection reset",
                     "failed to push some refs"):
            self.assertFalse(is_concurrent_push_rejection(
                SimpleNamespace(returncode=1,stderr=text,stdout="")))
        self.assertFalse(is_concurrent_push_rejection(
            SimpleNamespace(returncode=0,stderr="non-fast-forward",stdout="")))

if __name__=="__main__":unittest.main()
