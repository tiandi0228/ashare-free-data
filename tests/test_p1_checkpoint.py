import unittest
from collector.p1_checkpoint import merge,validate,epoch_path

class CheckpointTests(unittest.TestCase):
    def ledger(self,n):
        return {"phase":"P1_ROSTER_SHARD_LEDGER","trade_gate":"BLOCKED",
                "historical_PIT_verified":False,"orders":[],"executable_candidates":[],
                "source_sha256":"a"*64,"shard_count":2,
                "completed":[{"index":i,"issuer_count":8,"manifest_sha256":"b"*64,"receipt_sha256":"c"*64} for i in range(n)],
                "completed_shards":n,"completed_issuers":n*8,
                "pending_shards":list(range(n,2)), "next_shard":n if n<2 else None,
                "failed_in_this_reconciliation":[], "full_market_bars_certified":False}
    def test_epoch_checkpoint_is_content_addressed(self):
        self.assertEqual(epoch_path("a"*64),"evidence/checkpoints/"+"a"*64+".json")
        with self.assertRaises(ValueError):epoch_path("../invalid")
    def test_versioned_read_never_uses_other_epoch(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from collector import p1_checkpoint
        a=self.ledger(1)
        calls=[]
        def fake_read(repo,path=p1_checkpoint.CHECKPOINT):
            calls.append(path)
            if path==p1_checkpoint.CHECKPOINT:
                return a,"legacy_sha"
            return None,None
        with patch.object(p1_checkpoint,"remote_read",side_effect=fake_read):
            with tempfile.TemporaryDirectory() as d:
                with patch("sys.argv",["p1_checkpoint","--mode","read","--repo","test/repo","--source-sha","b"*64,"--out",str(Path(d)/"not_written.json")]):
                    p1_checkpoint.main()
                self.assertFalse((Path(d)/"not_written.json").exists())
        self.assertEqual(calls,[p1_checkpoint.epoch_path("b"*64),p1_checkpoint.CHECKPOINT])

    def test_higher_progress_is_preserved(self):
        self.assertEqual(merge(self.ledger(0),self.ledger(1))["completed_issuers"],8)
    def test_new_progress_wins(self):
        self.assertEqual(merge(self.ledger(2),self.ledger(1))["completed_issuers"],16)
    def test_other_roster_is_rejected(self):
        other=self.ledger(1);other["source_sha256"]="z"*64
        with self.assertRaises(ValueError):merge(self.ledger(2),other)
    def test_equal_count_replacement_rejected(self):
        newer=self.ledger(1)
        older=self.ledger(1)
        newer["completed"][0]["receipt_sha256"]="d"*64
        with self.assertRaises(ValueError):merge(newer,older)
    def test_stale_conflicting_evidence_rejected(self):
        stale=self.ledger(1);remote=self.ledger(2)
        stale["completed"][0]["receipt_sha256"]="d"*64
        with self.assertRaises(ValueError):merge(stale,remote)
    def test_stale_different_shard_rejected(self):
        stale=self.ledger(1);remote=self.ledger(1)
        remote["completed"].append({"index":1,"issuer_count":8,"manifest_sha256":"b"*64,"receipt_sha256":"c"*64})
        remote["completed_shards"]=2;remote["completed_issuers"]=16
        remote["pending_shards"]=[];remote["next_shard"]=None
        stale["completed"][0]["index"]=1
        stale["pending_shards"]=[0];stale["next_shard"]=0
        # Stale evidence for shard 1 matches, so retain the remote checkpoint.
        self.assertEqual(merge(stale,remote)["completed_issuers"],16)
    def test_stale_unknown_shard_rejected(self):
        stale=self.ledger(1);remote=self.ledger(1)
        stale["completed"][0]["index"]=1
        stale["pending_shards"]=[0];stale["next_shard"]=0
        with self.assertRaises(ValueError):merge(stale,remote)

    def test_added_shard_preserves_old_evidence(self):
        self.assertEqual(merge(self.ledger(2),self.ledger(1))["completed_issuers"],16)
    def test_out_of_range_shard_rejected(self):
        record=self.ledger(1)
        record["completed"][0]["index"]=record["shard_count"]
        with self.assertRaises(ValueError):validate(record)

    def test_pending_ledger_mismatch_rejected(self):
        record=self.ledger(1);record["pending_shards"]=[]
        with self.assertRaises(ValueError):validate(record)
    def test_next_shard_mismatch_rejected(self):
        record=self.ledger(1);record["next_shard"]=0
        with self.assertRaises(ValueError):validate(record)
    def test_invalid_evidence_digest_rejected(self):
        record=self.ledger(1);record["completed"][0]["manifest_sha256"]="z"*64
        with self.assertRaises(ValueError):validate(record)
    def test_unverified_cannot_claim_full_market(self):
        record=self.ledger(1);record["full_market_bars_certified"]=True
        with self.assertRaises(ValueError):validate(record)

    def test_invalid_failed_shard_rejected(self):
        for failed in ([2], [0,0], ["0"], None):
            with self.subTest(failed=failed):
                record=self.ledger(1);record["failed_in_this_reconciliation"]=failed
                with self.assertRaises(ValueError):validate(record)

    def test_same_count_different_completed_shard_rejected(self):
        candidate=self.ledger(1);previous=self.ledger(1)
        candidate["completed"][0]["index"]=1
        candidate["pending_shards"]=[0];candidate["next_shard"]=0
        with self.assertRaises(ValueError):merge(candidate,previous)

    def test_wrong_source_hash_rejected(self):
        record=self.ledger(1)
        record["source_sha256"]="not_a_sha"
        with self.assertRaises(ValueError):validate(record)

    def test_missing_checkpoint_requires_explicit_404(self):
        import subprocess
        from unittest.mock import patch
        from collector.p1_checkpoint import remote_read
        missing=subprocess.CalledProcessError(1,["gh","api"],stderr="gh: Not Found (HTTP 404)")
        auth=subprocess.CalledProcessError(1,["gh","api"],stderr="gh: Forbidden (HTTP 403)")
        with patch("collector.p1_checkpoint.gh",side_effect=missing):
            self.assertEqual(remote_read("a/b"),(None,None))
        with patch("collector.p1_checkpoint.gh",side_effect=auth):
            with self.assertRaises(subprocess.CalledProcessError):
                remote_read("a/b")

    def test_orders_rejected(self):
        candidate=self.ledger(0);candidate["orders"]=[{"buy":"SH"}]
        with self.assertRaises(ValueError):validate(candidate)
    def test_inconsistent_totals_rejected(self):
        candidate=self.ledger(1);candidate["completed_issuers"]=500
        with self.assertRaises(ValueError):validate(candidate)
if __name__=="__main__":unittest.main()
