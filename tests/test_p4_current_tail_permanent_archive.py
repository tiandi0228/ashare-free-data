import hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from collector.p4_current_tail_permanent_archive import prepare,stage,persist,readback

class DurableCurrentTailEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.epoch=self.root/"original"
        self.epoch.mkdir()
        self.source=self.root/"capture"
        self.source.mkdir()
        self.commit="a"*40
        self.code="sh.600000"
        self.original=b"date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n2026-10-20,sh.600000,10,10,10,10,100,1000,3,1\n"
        (self.source/"sh_600000_current.csv").write_bytes(self.original)
        self.report={
            "source_archive_commit":self.commit,
            "source_epoch_sha256":"5ba00fbd720fad90"+"a"*48,
            "frozen_p1_end":"2026-10-20",
            "as_of_day":"2026-10-30",
            "selected_codes":[self.code],"selected_issuers":1,
            "trade_gate":"BLOCKED","orders":[],
            "non_executable_ma20_crossing_events":[],
            "strategy_buy_signals_certified":0}
        (self.epoch/"archive_status.json").write_text(json.dumps({
            "source_sha256":self.report["source_epoch_sha256"],"trade_gate":"BLOCKED"}))
        self.write_report()
        self.checked={"phase":"P4_CURRENT_TAIL_INDEPENDENT_REPLAY",
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "buy_signals_authorized":0,"verified_issuers":1,
            "new_rows_verified":0,"verified_non_executable_crossings":0}
        patcher=patch("collector.p4_current_tail_permanent_archive.verify",
                      return_value=self.checked)
        self.verified=patcher.start()
        self.addCleanup(patcher.stop)
    def write_report(self):
        (self.source/"current_tail_report.json").write_text(json.dumps(self.report))
    def prepared(self):
        return prepare(self.epoch,self.source,"41158581207",1,self.commit)
    def test_full_byte_hashes_and_non_executable_receipt(self):
        path,files,receipt=self.prepared()
        self.assertIn("run_41158581207_attempt_1",path)
        self.assertEqual(set(files),{"current_tail_report.json",
            "sh_600000_current.csv","independent_verification.json","permanent_receipt.json"})
        self.assertEqual(files["sh_600000_current.csv"],self.original)
        self.assertEqual(receipt["immutable_original_sha256"]["sh_600000_current.csv"],
                         hashlib.sha256(self.original).hexdigest())
        self.assertEqual(receipt["trade_gate"],"BLOCKED")
        self.assertEqual(receipt["orders"],[])
        self.assertFalse(receipt["trading_signal_authorized"])
        self.assertFalse(receipt["full_market_coverage"])
        self.assertEqual(receipt["non_executable_ma20_crossings"],0)
        self.verified.assert_called_once_with(self.epoch,self.source)
    def test_stage_idempotence_but_conflicting_old_byte_fails(self):
        path,files,_=self.prepared()
        dest=stage(self.root/"archive",path,files)
        self.assertTrue(dest.joinpath("permanent_receipt.json").is_file())
        stage(self.root/"archive",path,files)
        dest.joinpath("sh_600000_current.csv").write_bytes(b"forged")
        with self.assertRaisesRegex(ValueError,"immutable current-tail archive conflict"):
            stage(self.root/"archive",path,files)
    def test_permanent_readback_recomputes_all_source_bytes(self):
        path,files,_=self.prepared()
        stage(self.root/"archive",path,files)
        result=readback(self.root/"archive",self.epoch,41158581207,1,self.commit)
        self.assertEqual(result["status"],"PERMANENT_READBACK_VERIFIED")
        self.assertEqual(result["verified_issuers"],1)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        (self.root/"archive"/path/"independent_verification.json").write_text("tampered")
        with self.assertRaisesRegex(ValueError,"permanent archive bytes mismatch"):
            readback(self.root/"archive",self.epoch,41158581207,1,self.commit)

    def test_missing_permanent_report_cannot_be_read_back(self):
        path,files,_=self.prepared()
        stage(self.root/"archive",path,files)
        (self.root/"archive"/path/"permanent_receipt.json").unlink()
        with self.assertRaisesRegex(ValueError,"permanent archive files incomplete"):
            readback(self.root/"archive",self.epoch,41158581207,1,self.commit)

    def test_staged_extra_unlisted_file_rejected(self):
        path,files,_=self.prepared()
        dest=stage(self.root/"archive",path,files)
        (dest/"hidden.txt").write_text("unexpected")
        with self.assertRaisesRegex(ValueError,"unexpected pre-existing"):
            stage(self.root/"archive",path,files)
    def test_archive_commit_must_match_capture(self):
        with self.assertRaisesRegex(ValueError,"capture archive commit changed"):
            prepare(self.epoch,self.source,1,1,"b"*40)
    def test_verify_failure_blocks_before_any_archival_files(self):
        self.verified.side_effect=ValueError("forged event")
        with self.assertRaisesRegex(ValueError,"forged event"):
            self.prepared()
        self.assertFalse((self.root/"archive").exists())
    def test_unsafe_trading_receipt_fails_before_archive(self):
        self.checked["buy_signals_authorized"]=1
        with self.assertRaisesRegex(ValueError,"research evidence failed"):
            self.prepared()
    def test_bad_id_and_unbounded_issuers_fail(self):
        for run,attempt in ((0,1),(-3,1),(2,0),(2,101)):
            with self.subTest(run=run,attempt=attempt):
                with self.assertRaisesRegex(ValueError,"invalid evidence"):
                    prepare(self.epoch,self.source,run,attempt,self.commit)
        self.report["selected_codes"]=["sh.600000"]*9
        self.write_report()
        with self.assertRaisesRegex(ValueError,"non-bounded"):
            self.prepared()
    def test_git_push_uses_askpass_without_token_in_command_and_readback(self):
        commands=[]
        def fake_git(*args,cwd=None,env=None,check=True):
            commands.append((args,cwd,env))
            if args[0]=="rev-parse":
                return SimpleNamespace(stdout=self.commit+"\n",returncode=0)
            if args[0]=="clone":
                Path(args[-1]).mkdir(parents=True)
            if args[0]=="diff":
                return SimpleNamespace(stdout="",returncode=1)
            if args[0]=="ls-remote":
                return SimpleNamespace(stdout=self.commit+" refs/heads/research-csv-archive\n",returncode=0)
            return SimpleNamespace(stdout="",returncode=0)
        with patch("collector.p4_current_tail_permanent_archive.git",side_effect=fake_git):
            with patch.dict("os.environ",{"GH_TOKEN":"super_secret_value"}):
                out=persist(self.epoch,self.source,"owner/repo",103,2,self.commit)
        self.assertTrue(out["persisted"])
        self.assertIn("run_103_attempt_2",out["path"])
        self.assertEqual(out["trade_gate"],"BLOCKED")
        self.assertTrue(any(x[0][0]=="push" for x in commands))
        for cmd,_,_ in commands:
            self.assertNotIn("super_secret_value"," ".join(cmd))
        push=next(x for x in commands if x[0][0]=="push")
        self.assertIn("GIT_ASKPASS",push[2])
    def test_pinned_commit_mismatch_rejected_before_clone(self):
        with patch("collector.p4_current_tail_permanent_archive.git",
                   return_value=SimpleNamespace(stdout="b"*40,returncode=0)) as g:
            with patch.dict("os.environ",{"GH_TOKEN":"token"}):
                with self.assertRaisesRegex(ValueError,"pinned baseline"):
                    persist(self.epoch,self.source,"owner/repo",1,1,self.commit)
        self.assertEqual(g.call_count,1)
    def test_unexpected_repository_and_no_token_rejected(self):
        with self.assertRaisesRegex(ValueError,"untrusted repository"):
            persist(self.epoch,self.source,"bad&repo",1,1,self.commit)
        with patch.dict("os.environ",{"GH_TOKEN":""}):
            with self.assertRaisesRegex(ValueError,"token unavailable"):
                persist(self.epoch,self.source,"owner/repo",1,1,self.commit)

if __name__=="__main__":
    unittest.main()
