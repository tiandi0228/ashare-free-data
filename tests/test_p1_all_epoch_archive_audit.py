import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_all_epoch_archive_audit import examine


class AllEpochArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.epoch=self.root/("a"*16)
        self.shard=self.epoch/"shard_0007"
        self.shard.mkdir(parents=True)
        self.csv=self.shard/"sh_600000.csv"
        self.csv.write_text("date,code\n2025-01-01,sh.600000\n")
        self.receipt={
            "status":"OBSERVED_SUBSET_UNVERIFIED",
            "trade_gate":"BLOCKED","orders":[],
            "historical_point_in_time_universe_verified":False,
            "issuer_count":1,
            "results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED",
                        "sha256":hashlib.sha256(self.csv.read_bytes()).hexdigest()}]
        }
        (self.shard/"quality.json").write_text(json.dumps(self.receipt))
        self.status=self.epoch/"archive_status.json"
        self.status.write_text(json.dumps({
            "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[7]}))

    def test_valid_archive_is_research_only(self):
        result=examine(self.root)
        self.assertEqual(result["status"],"ALL_EPOCH_SOURCE_ORIGINALS_SHA_VERIFIED")
        self.assertEqual(result["verified_original_shards"],1)
        self.assertEqual(result["verified_original_csv_files"],1)
        self.assertEqual(result["issue_count"],0)
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertFalse(result["destination_mirror_verified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_status_claims_unpersisted_shard(self):
        self.status.write_text(json.dumps({
            "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[7,8]}))
        result=examine(self.root)
        self.assertEqual(result["status"],"SOURCE_ARCHIVE_INCOMPLETE")
        self.assertEqual(result["verified_original_shards"],1)
        self.assertEqual(result["invalid_originals"],1)
        self.assertFalse(result["source_archive_sha_verified"])

    def test_tampered_csv_or_extra_file_is_rejected(self):
        self.csv.write_text("changed")
        self.assertEqual(examine(self.root)["verified_original_shards"],0)
        self.csv.write_text("date,code\n2025-01-01,sh.600000\n")
        (self.shard/"unexpected.csv").write_text("unknown")
        self.assertEqual(examine(self.root)["verified_original_shards"],0)

    def test_duplicate_indices_and_unlisted_shards_fail(self):
        self.status.write_text(json.dumps({
            "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[7,7]}))
        self.assertGreater(examine(self.root)["issue_count"],0)
        self.status.write_text(json.dumps({
            "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[7]}))
        (self.epoch/"shard_0008").mkdir()
        self.assertEqual(examine(self.root)["unlisted_original_receipts"],1)

    def test_other_research_data_folders_are_not_p1_epochs(self):
        (self.root/"p4-current-tail").mkdir()
        (self.root/"p4-tail-backfill").mkdir()
        result=examine(self.root)
        self.assertEqual(result["status"],"ALL_EPOCH_SOURCE_ORIGINALS_SHA_VERIFIED")
        self.assertEqual(result["epoch_count"],1)
        self.assertEqual(result["non_p1_data_directories"],
                         ["p4-current-tail","p4-tail-backfill"])
        self.assertEqual(result["issue_count"],0)

    def test_missing_source_never_approves(self):
        result=examine(self.root/"not-here")
        self.assertFalse(result["source_archive_sha_verified"])
        self.assertEqual(result["orders"],[])


if __name__=="__main__":
    unittest.main()
