"""Offline rehearsal tests with real checked-in P1 roster and checkpoint bytes."""
import copy
import json
import unittest
from pathlib import Path

from collector.p1_checkpoint import epoch_path
from collector.p1_live_gap_rehearsal import rehearse

ROOT=Path(__file__).resolve().parents[1]

class LiveGapRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock=json.loads((ROOT/"evidence/p1_active_roster.json").read_text())
        cls.ledger=json.loads((ROOT/epoch_path(cls.lock["source_sha256"])).read_text())
        cls.archive={"source_sha256":cls.lock["source_sha256"],
                     "trade_gate":"BLOCKED",
                     "archived_shards":[x["index"] for x in cls.ledger["completed"]]}

    def fetch(self,repo,path,ref):
        self.assertEqual(repo,"tiandi0228/ashare-free-data")
        if path=="evidence/p1_active_roster.json" and ref=="main":
            return self.lock
        if path==epoch_path(self.lock["source_sha256"]) and ref=="main":
            return self.ledger
        if ref=="research-csv-archive" and path==self.lock["source_sha256"][:16]+"/archive_status.json":
            return self.archive
        self.fail("unexpected request "+str((path,ref)))

    def test_real_roster_replayed_and_missing_only(self):
        result=rehearse("tiandi0228/ashare-free-data",self.fetch)
        done={x["index"] for x in self.ledger["completed"]}
        self.assertEqual(result["active_completed_shards"],self.ledger["completed_shards"])
        self.assertTrue(all(x not in done for x in result["proposed_manual_shards"]))
        self.assertGreaterEqual(len(result["proposed_manual_shards"]),1)
        self.assertLessEqual(len(result["proposed_manual_shards"]),2)
        self.assertTrue(result["original_roster_SHA_replayed"])
        self.assertEqual(result["vendor_requests"],0)
        self.assertEqual(result["archive_writes"],0)
        self.assertFalse(result["permission_to_write_or_trade"])
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_stale_second_checkpoint_fails(self):
        calls={"count":0}
        def fetch(repo,path,ref):
            if path==epoch_path(self.lock["source_sha256"]):
                calls["count"]+=1
                if calls["count"]>1:
                    x=copy.deepcopy(self.ledger)
                    idx=x["pending_shards"][0]
                    x["completed"].append({"index":idx,"issuer_count":8,
                        "manifest_sha256":"f"*64,"receipt_sha256":"e"*64})
                    x["completed_shards"]+=1
                    x["completed_issuers"]+=8
                    x["pending_shards"]=x["pending_shards"][1:]
                    x["next_shard"]=x["pending_shards"][0] if x["pending_shards"] else None
                    return x
            return self.fetch(repo,path,ref)
        with self.assertRaises(ValueError):
            rehearse("tiandi0228/ashare-free-data",fetch)

    def test_archive_replay_gap_denied(self):
        bad=copy.deepcopy(self.archive)
        bad["archived_shards"].pop()
        def fetch(repo,path,ref):
            return bad if ref=="research-csv-archive" else self.fetch(repo,path,ref)
        with self.assertRaises(ValueError):
            rehearse("tiandi0228/ashare-free-data",fetch)

    def test_mismatched_original_roster_denied(self):
        lock=copy.deepcopy(self.lock)
        lock["source_sha256"]="0"*64
        def fetch(repo,path,ref):
            return lock if path=="evidence/p1_active_roster.json" else self.fetch(repo,path,ref)
        with self.assertRaises(ValueError):
            rehearse("tiandi0228/ashare-free-data",fetch)

if __name__=="__main__":
    unittest.main()
