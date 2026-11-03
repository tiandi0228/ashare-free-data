"""Offline test: immutable snapshot archive never authorizes orders."""
import base64,json,unittest
from unittest.mock import patch
from collector.intraday_snapshot_archive import validate,persist,ensure_branch,BRANCH,WATCHLIST

def sample():
    symbols={code:dict(validation=dict(trade_gate="BLOCKED",orders=[],
               executable_candidates=[],executable_quote=False))
             for code in WATCHLIST}
    symbols["301015"]=dict(status="SOURCE_UNAVAILABLE",
                            trade_gate="BLOCKED",orders=[],
                            executable_candidates=[],executable_quote=False)
    return dict(phase="P1_PUBLIC_INTRADAY_RESEARCH_SNAPSHOT",
                asof="2026-11-03T13:37:36+08:00",
                provider_type="UNOFFICIAL_WEB_ENDPOINTS",
                trade_gate="BLOCKED",orders=[],executable_candidates=[],
                symbols=symbols)
def raw():return json.dumps(sample(),sort_keys=True).encode()

class ArchiveTests(unittest.TestCase):
    def test_path_includes_day_run_attempt(self):
        path,body=validate(raw(),123,2)
        self.assertEqual(path,"snapshots/2026-11-03/run_123_attempt_2.json")
        self.assertEqual(body["symbols"]["301015"]["status"],"SOURCE_UNAVAILABLE")

    def test_global_gate_or_order_must_fail_closed(self):
        for key,val in (("trade_gate","OPEN"),("orders",[1]),
                        ("executable_candidates",["002249"])):
            body=sample();body[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate(json.dumps(body).encode(),123,1)

    def test_forged_executable_symbol_rejected(self):
        body=sample();body["symbols"]["002249"]["validation"]["executable_quote"]=True
        with self.assertRaises(ValueError):validate(json.dumps(body).encode(),123,1)

    def test_missing_stock_and_naive_time_rejected(self):
        body=sample();del body["symbols"]["300896"]
        with self.assertRaises(ValueError):validate(json.dumps(body).encode(),123,1)
        body=sample();body["asof"]="2026-11-03T13:37:36"
        with self.assertRaises(ValueError):validate(json.dumps(body).encode(),123,1)

    def test_create_only_and_readback(self):
        data=raw();path,_=validate(data,123,1)
        saved=dict(path=path,sha="blob",content=base64.b64encode(data).decode())
        with patch("collector.intraday_snapshot_archive.ensure_branch"):
            with patch("collector.intraday_snapshot_archive.api",side_effect=[
                    None,{},saved]) as api:
                result=persist("test/repo",path,data)
        self.assertEqual(api.call_count,3)
        payload=api.call_args_list[1].kwargs["data"]
        self.assertEqual(payload["branch"],BRANCH)
        self.assertNotIn("sha",payload)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertFalse(result["replayable_minute_bars"])

    def test_duplicate_same_bytes_no_write(self):
        data=raw();path,_=validate(data,123,1)
        saved=dict(path=path,sha="blob",content=base64.b64encode(data).decode())
        with patch("collector.intraday_snapshot_archive.ensure_branch"):
            with patch("collector.intraday_snapshot_archive.api",side_effect=[
                    saved,saved]) as api:
                persist("test/repo",path,data)
        self.assertEqual(api.call_count,2)
        self.assertTrue(all(c.kwargs.get("method","GET")=="GET"
                            for c in api.call_args_list))

    def test_duplicate_conflict_refused(self):
        data=raw();path,_=validate(data,123,1)
        saved=dict(path=path,sha="blob",content=base64.b64encode(b"{}").decode())
        with patch("collector.intraday_snapshot_archive.ensure_branch"):
            with patch("collector.intraday_snapshot_archive.api",
                       side_effect=[saved,saved]):
                with self.assertRaisesRegex(ValueError,"differs"):
                    persist("test/repo",path,data)

    def test_invalid_repo_and_path_refused(self):
        with self.assertRaises(ValueError):persist("bad repo","bad",raw())
        with self.assertRaises(ValueError):persist("test/repo","../secrets",raw())

    def test_branch_seed(self):
        with patch("collector.intraday_snapshot_archive.api",side_effect=[
                None,{"object":{"sha":"a"*40}},
                {"ref":"refs/heads/"+BRANCH}]) as api:
            ensure_branch("test/repo")
        self.assertEqual(api.call_args_list[2].kwargs["method"],"POST")

if __name__=="__main__":unittest.main()
