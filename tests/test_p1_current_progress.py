"""P1 progress must come from current source epoch, not a cached narrative."""
import copy
import unittest
from unittest.mock import patch

from collector.p1_current_progress import report, capture

SHA="a"*64

def inputs():
    lock={"source_sha256":SHA,"source_requested_day":"2026-11-02",
          "created_run_id":123,"original_quality":{"mainboard_prefix_rows":16}}
    checkpoint={"phase":"P1_ROSTER_SHARD_LEDGER","trade_gate":"BLOCKED",
        "historical_PIT_verified":False,"orders":[],"executable_candidates":[],
        "source_sha256":SHA,"shard_count":2,
        "completed":[{"index":0,"issuer_count":8,"manifest_sha256":"b"*64,
                      "receipt_sha256":"c"*64}],
        "completed_shards":1,"completed_issuers":8,
        "pending_shards":[1],"next_shard":1,
        "failed_in_this_reconciliation":[],"full_market_bars_certified":False}
    return lock,checkpoint

class P1CurrentProgressTests(unittest.TestCase):
    def test_valid_pinned_checkpoint_count(self):
        a,b=inputs()
        with patch("collector.p1_current_progress.unpack",return_value=(b"csv",{})):
            r=report(a,b)
        self.assertEqual(r["completed_shards"],1)
        self.assertEqual(r["total_shards"],2)
        self.assertEqual(r["pending_issuers"],8)
        self.assertEqual(r["research_coverage_percent"],50)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["historical_PIT_verified"])
    def test_different_source_and_forged_counts_rejected(self):
        for mutate in (
            lambda a,b: b.update(source_sha256="d"*64),
            lambda a,b: b.update(completed_shards=2),
            lambda a,b: b.update(completed_issuers=999),
            lambda a,b: b.update(trade_gate="OPEN"),
            lambda a,b: a["original_quality"].update(mainboard_prefix_rows=30),
            lambda a,b: b["completed"][0].update(receipt_sha256="BAD"),
        ):
            with self.subTest(mutate=mutate):
                a,b=inputs();mutate(a,b)
                with patch("collector.p1_current_progress.unpack",return_value=(b"csv",{})):
                    with self.assertRaises(ValueError):
                        report(a,b)
    def test_github_contents_base64_wrapping_decodes_strictly(self):
        import base64
        import json
        from types import SimpleNamespace
        from collector.p1_current_progress import remote_json
        payload=json.dumps({"phase":"EXACT","value":17}).encode()
        encoded=base64.b64encode(payload).decode()
        wrapped=encoded[:12]+"\\n"+encoded[12:]
        with patch("collector.p1_current_progress.subprocess.run",
                   return_value=SimpleNamespace(stdout=json.dumps({"content":wrapped}))):
            self.assertEqual(remote_json("owner/repo","evidence/test.json"),
                             {"phase":"EXACT","value":17})

    def test_invalid_contents_base64_still_rejected(self):
        import json
        from types import SimpleNamespace
        from collector.p1_current_progress import remote_json
        with patch("collector.p1_current_progress.subprocess.run",
                   return_value=SimpleNamespace(stdout=json.dumps({"content":"%%%"}))):
            with self.assertRaises(ValueError):
                remote_json("owner/repo","evidence/test.json")

    def test_current_epoch_only_no_stale_fallback(self):
        lock,ledger=inputs()
        paths=[]
        def fetch(repo,path):
            paths.append(path)
            return lock if path=="evidence/p1_active_roster.json" else ledger
        with patch("collector.p1_current_progress.remote_json",side_effect=fetch),patch(
                "collector.p1_current_progress.unpack",return_value=(b"csv",{})):
            r=capture("demo/repo")
        self.assertEqual(r["completed_shards"],1)
        self.assertEqual(paths,["evidence/p1_active_roster.json",
            "evidence/checkpoints/"+SHA+".json"])

if __name__=="__main__":
    unittest.main()
