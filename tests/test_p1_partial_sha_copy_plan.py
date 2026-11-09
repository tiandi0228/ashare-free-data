import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from collector.p1_partial_sha_copy_plan import plan

ACTIVE="a"*64
OLD="b"*64


def build_epoch(root,sha,missing=()):
    folder=Path(root)/sha[:16];folder.mkdir()
    (folder/"archive_status.json").write_text(json.dumps({
        "source_sha256":sha,"trade_gate":"BLOCKED",
        "archived_shards":[0,1]}))
    for i in (0,1):
        shard=folder/f"shard_{i:04d}";shard.mkdir()
        csv=shard/f"sh_{600000+i}.csv"
        csv.write_text(f"date,code\\n2026-10-20,sh.{600000+i}\\n")
        if i not in missing:
            (shard/"quality.json").write_text(json.dumps({
                "status":"OBSERVED_SUBSET_UNVERIFIED",
                "trade_gate":"BLOCKED",
                "historical_point_in_time_universe_verified":False,
                "orders":[],"issuer_count":1,
                "results":[{
                    "code":f"sh.{600000+i}","status":"OBSERVED_UNVERIFIED",
                    "sha256":hashlib.sha256(csv.read_bytes()).hexdigest()
                }]
            }))
    return folder


class PartialResearchPlanTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.active=build_epoch(self.root,ACTIVE)
        self.old=build_epoch(self.root,OLD,missing=(1,))

    def test_only_complete_source_sha_shards_are_planned(self):
        result=plan(self.root,ACTIVE)
        self.assertEqual(result["eligible_shards"],3)
        self.assertEqual(result["eligible_original_files"],6)
        self.assertEqual(result["quarantined_shards"],1)
        self.assertEqual(result["quarantine"][0]["shard_id"],"shard_0001")
        self.assertEqual(result["quarantine"][0]["reason"],"QUALITY_RECEIPT_MISSING")
        self.assertFalse(result["entire_legacy_archive_eligible"])
        self.assertFalse(result["automatic_copy_authorized"])
        self.assertFalse(result["destination_files_verified"])
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertEqual(result["executable_candidates"],[])
        self.assertEqual(len(result["eligible_source_shards"]),3)
        self.assertTrue(all(not x["historical_PIT_verified"]
                            for x in result["eligible_source_shards"]))

    def test_csv_tamper_quarantines_entire_shard_not_remaining_files(self):
        target=self.active/"shard_0000/sh_600000.csv"
        target.write_text("corrupt")
        result=plan(self.root,ACTIVE)
        self.assertEqual(result["eligible_shards"],2)
        self.assertEqual(result["quarantined_shards"],2)
        self.assertIn("QUALITY_OR_CSV_SHA_NOT_RECONCILED",
                      [x["reason"] for x in result["quarantine"]])
        self.assertFalse(result["writer_cutover_authorized"])

    def test_forged_receipt_no_historical_pit_and_extra_csv_blocked(self):
        receipt=self.active/"shard_0000/quality.json"
        payload=json.loads(receipt.read_text())
        payload["historical_point_in_time_universe_verified"]=True
        receipt.write_text(json.dumps(payload))
        result=plan(self.root,ACTIVE)
        self.assertEqual(result["quarantined_shards"],2)
        self.assertFalse(result["automatic_copy_authorized"])

    def test_missing_epoch_rejected(self):
        with self.assertRaises(ValueError):plan(self.root,"c"*64)
        data=json.loads((self.old/"archive_status.json").read_text())
        data["trade_gate"]="OPEN"
        (self.old/"archive_status.json").write_text(json.dumps(data))
        with self.assertRaises(ValueError):plan(self.root,ACTIVE)

    def test_symlinks_and_unadvertised_shard_rejected(self):
        extra=self.old/"shard_0002";extra.mkdir()
        with self.assertRaises(ValueError):plan(self.root,ACTIVE)
        extra.rmdir()
        symlink=self.active/"shard_0000/sh_600000.csv"
        symlink.unlink()
        symlink.symlink_to(self.active/"shard_0001/sh_600001.csv")
        result=plan(self.root,ACTIVE)
        self.assertEqual(result["quarantined_shards"],2)
        self.assertFalse(result["writer_cutover_authorized"])

    def test_does_not_mutate_source(self):
        original=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        plan(self.root,ACTIVE)
        after=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(original,after)


if __name__=="__main__":
    unittest.main()
