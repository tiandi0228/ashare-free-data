import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from collector.p1_archive_migration_readiness import examine

class MigrationReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.epoch="a"*64
        self.folder=self.root/self.epoch[:16]/"shard_0000"
        self.folder.mkdir(parents=True)
        self.csv=self.folder/"sh_600000.csv"
        self.csv.write_text("date,code\n2025-12-31,sh.600000\n")
        self.receipt={
            "status":"OBSERVED_SUBSET_UNVERIFIED",
            "trade_gate":"BLOCKED",
            "historical_point_in_time_universe_verified":False,
            "orders":[],"issuer_count":1,"manifest_sha256":"b"*64,
            "results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED",
                        "sha256":hashlib.sha256(self.csv.read_bytes()).hexdigest()}]
        }
        (self.folder/"quality.json").write_text(json.dumps(self.receipt))
        canonical=hashlib.sha256(json.dumps(self.receipt,sort_keys=True,
                                             ensure_ascii=False).encode()).hexdigest()
        self.checkpoint={
            "phase":"P1_ROSTER_SHARD_LEDGER","source_sha256":self.epoch,
            "shard_count":2,"completed":[{
                "index":0,"issuer_count":1,"manifest_sha256":"b"*64,
                "receipt_sha256":canonical}],
            "completed_shards":1,"completed_issuers":1,
            "pending_shards":[1],"next_shard":1,"failed_in_this_reconciliation":[],
            "full_market_bars_certified":False,"historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]
        }

    def test_absent_active_epoch_is_explicit_blocker(self):
        result=examine(self.checkpoint,self.root)
        self.assertEqual(result["status"],"ACTIVE_EPOCH_ARCHIVE_NOT_FOUND")
        self.assertEqual(result["missing_or_invalid_shard_count"],1)
        self.assertFalse(result["writer_cutover_authorized"])

    def test_complete_originals_replayed_but_cutover_stays_blocked(self):
        (self.folder.parent/"archive_status.json").write_text(json.dumps({
            "source_sha256":self.epoch,"trade_gate":"BLOCKED",
            "archived_shards":[0]
        }))
        result=examine(self.checkpoint,self.root)
        self.assertEqual(result["status"],"CHECKPOINT_SOURCE_ORIGINALS_PRESENT_SHA_VERIFIED")
        self.assertEqual(result["verified_original_shards"],1)
        self.assertEqual(result["verified_original_csv_files"],1)
        self.assertTrue(result["all_checkpoint_originals_durably_located"])
        self.assertFalse(result["destination_mirror_verified"])
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertEqual(result["orders"],[])

    def test_corrupt_csv_and_ledger_receipt_fail_without_trading(self):
        (self.folder.parent/"archive_status.json").write_text(json.dumps({
            "source_sha256":self.epoch,"trade_gate":"BLOCKED",
            "archived_shards":[0]
        }))
        self.csv.write_text("tampered")
        a=examine(self.checkpoint,self.root)
        self.assertEqual(a["status"],"CHECKPOINT_ORIGINALS_INCOMPLETE_NO_CUTOVER")
        self.assertEqual(a["verified_original_shards"],0)
        self.assertFalse(a["writer_cutover_authorized"])
        self.csv.write_text("date,code\n2025-12-31,sh.600000\n")
        self.checkpoint["completed"][0]["receipt_sha256"]="f"*64
        b=examine(self.checkpoint,self.root)
        self.assertEqual(b["status"],"CHECKPOINT_ORIGINALS_INCOMPLETE_NO_CUTOVER")

    def test_invalid_checkpoint_fails_closed(self):
        self.checkpoint["orders"]=[{"unsafe":True}]
        with self.assertRaises(ValueError):
            examine(self.checkpoint,self.root)

if __name__=="__main__":unittest.main()
