import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from collector.p1_legacy_receipt_gap_inventory import inventory_missing_receipts

class LegacyReceiptGapInventoryTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.epoch=self.root/("a"*16)
        self.shard=self.epoch/"shard_0024"
        self.shard.mkdir(parents=True)
        self.bytes=b"date,code\n2024-10-21,sh.600258\n"
        (self.shard/"sh_600258.csv").write_bytes(self.bytes)
        (self.epoch/"archive_status.json").write_text(json.dumps({
            "source_sha256":"a"*64,"trade_gate":"BLOCKED",
            "archived_shards":[24],
        }))

    def test_missing_receipt_keeps_raw_csv_hash_without_fabrication(self):
        result=inventory_missing_receipts(self.root)
        self.assertEqual(result["missing_original_receipts"],1)
        self.assertEqual(result["scanned_source_statuses"],1)
        self.assertFalse(result["all_epoch_archive_complete"])
        self.assertEqual(result["retained_original_csv_files"],1)
        gap=result["gaps"][0]
        self.assertEqual(gap["shard_index"],24)
        self.assertFalse(gap["original_receipt_recovered"])
        self.assertEqual(gap["original_csv_files"][0]["sha256"],
                         hashlib.sha256(self.bytes).hexdigest())
        self.assertEqual(gap["original_csv_files"][0]["bytes"],len(self.bytes))
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertFalse((self.shard/"quality.json").exists())

    def test_present_original_receipt_excluded_without_overwriting(self):
        original=b'{"original":true}'
        (self.shard/"quality.json").write_bytes(original)
        result=inventory_missing_receipts(self.root)
        self.assertEqual(result["missing_original_receipts"],0)
        self.assertEqual((self.shard/"quality.json").read_bytes(),original)
        self.assertEqual(result["status"],"NO_MISSING_RECEIPTS_IN_SCANNED_STATUSES")
        self.assertFalse(result["all_epoch_archive_complete"])

    def test_stray_shard_content_fails_closed(self):
        (self.shard/"unknown.txt").write_text("unsafe")
        with self.assertRaisesRegex(ValueError,"unexpected original"):
            inventory_missing_receipts(self.root)

    def test_one_missing_epoch_status_with_other_valid_epoch_is_not_hidden(self):
        other=self.root/("b"*16)
        other.mkdir()
        (other/"archive_status.json").write_text(json.dumps({
            "source_sha256":"b"*64,"trade_gate":"BLOCKED","archived_shards":[]
        }))
        (self.epoch/"archive_status.json").unlink()
        r=inventory_missing_receipts(self.root)
        self.assertEqual(r["scanned_source_statuses"],1)
        self.assertEqual(r["status"],"MISSING_EPOCH_STATUSES")
        self.assertEqual(r["missing_epoch_statuses"],["a"*16])
        self.assertFalse(r["all_epoch_archive_complete"])

    def test_missing_status_and_receipts_are_both_reported(self):
        other=self.root/("b"*16)
        other.mkdir()
        (self.epoch/"archive_status.json").unlink()
        (other/"archive_status.json").write_text(json.dumps({
            "source_sha256":"b"*64,"trade_gate":"BLOCKED","archived_shards":[1]
        }))
        r=inventory_missing_receipts(self.root)
        self.assertEqual(r["status"],"MISSING_EPOCH_STATUSES_AND_RECEIPTS")
        self.assertEqual(r["missing_original_receipts"],1)
        self.assertEqual(r["missing_epoch_status_count"],1)
        self.assertFalse(r["writer_cutover_authorized"])

    def test_missing_status_not_a_recovered_original(self):
        (self.epoch/"archive_status.json").unlink()
        result=inventory_missing_receipts(self.root)
        self.assertEqual(result["missing_original_receipts"],0)
        self.assertEqual(result["status"],"MISSING_EPOCH_STATUSES")
        self.assertEqual(result["missing_epoch_statuses"],["a"*16])
        self.assertEqual(result["missing_epoch_status_count"],1)
        self.assertEqual(result["scanned_source_statuses"],0)
        self.assertFalse(result["all_epoch_archive_complete"])
        self.assertFalse(result["original_receipt_authenticity_certified"])
        self.assertFalse(result["writer_cutover_authorized"])

if __name__=="__main__":
    unittest.main()
