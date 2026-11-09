import copy
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_legacy_original_receipt_gap_audit import inspect

ACTIVE="a"*64
OLD="b"*64


def epoch(root,sha,shards,quality):
    p=Path(root)/sha[:16]
    p.mkdir()
    (p/"archive_status.json").write_text(json.dumps({
        "source_sha256":sha,"archived_shards":shards,"trade_gate":"BLOCKED"}))
    for i in shards:
        folder=p/f"shard_{i:04d}";folder.mkdir()
        (folder/f"sh_{600000+i}.csv").write_text("date,code\n2026-10-20,test\n")
        if i in quality:
            (folder/"quality.json").write_text('{"status":"OBSERVED_SUBSET_UNVERIFIED"}')
    return p


class SourceLegacyGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.active=epoch(self.root,ACTIVE,[0,1],{0,1})
        self.old=epoch(self.root,OLD,[24,25],{24})

    def test_reports_precise_legacy_missing_receipt_not_auto_repair(self):
        result=inspect(self.root,ACTIVE)
        self.assertEqual(result["status"],"LEGACY_QUALITY_RECEIPT_GAPS_NO_CUTOVER")
        self.assertEqual(result["epochs_observed"],2)
        self.assertEqual(result["original_csv_files_observed"],4)
        self.assertEqual(result["missing_receipts_total"],1)
        self.assertEqual(result["missing_original_receipts"],[{
            "source_epoch_prefix":OLD[:16],"shard_id":"shard_0025",
            "reason":"ORIGINAL_QUALITY_RECEIPT_MISSING_NOT_RECONSTRUCTIBLE"}])
        active=next(e for e in result["epochs"] if e["is_active_source_epoch"])
        self.assertEqual(active["missing_quality_receipts"],0)
        self.assertFalse(result["missing_receipts_synthesized"])
        self.assertFalse(result["original_csv_bytes_sha_verified_by_this_report"])
        self.assertFalse(result["destination_mirror_verified"])
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_missing_receipts_must_not_silently_disappear(self):
        path=self.old/"shard_0025/quality.json"
        before=inspect(self.root,ACTIVE)
        self.assertFalse(path.exists())
        self.assertEqual(before["missing_receipts_total"],1)
        path.write_text('{"status":"OBSERVED_SUBSET_UNVERIFIED"}')
        after=inspect(self.root,ACTIVE)
        self.assertEqual(after["missing_receipts_total"],0)
        self.assertEqual(after["status"],"ALL_EPOCH_RECEIPTS_PRESENT_NOT_BYTE_VERIFIED")
        self.assertFalse(after["writer_cutover_authorized"])

    def test_forged_epoch_and_unsafe_trade_gate_rejected(self):
        path=self.old/"archive_status.json"
        original=json.loads(path.read_text())
        for changes in (
            {"trade_gate":"OPEN"},
            {"source_sha256":"c"*64},
            {"archived_shards":[24,24]},
            {"archived_shards":[24,True]},
        ):
            path.write_text(json.dumps({**original,**changes}))
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                inspect(self.root,ACTIVE)
        path.write_text(json.dumps(original))
        with self.assertRaises(ValueError):
            inspect(self.root,"c"*64)

    def test_unadvertised_archive_shard_and_symlink_rejected(self):
        extra=self.old/"shard_0030";extra.mkdir()
        with self.assertRaises(ValueError):inspect(self.root,ACTIVE)
        extra.rmdir()
        external=self.root/"outside.csv";external.write_text("tampered")
        link=self.old/"shard_0025/external.csv";link.symlink_to(external)
        with self.assertRaises(ValueError):inspect(self.root,ACTIVE)

    def test_report_is_read_only_and_never_claims_sha_certification(self):
        original=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        result=inspect(self.root,ACTIVE)
        after=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(original,after)
        self.assertTrue(all(e["all_source_bytes_sha_verified_by_this_report"] is False
                            for e in result["epochs"]))
        self.assertFalse(result["historical_PIT_verified"])


if __name__=="__main__":
    unittest.main()
