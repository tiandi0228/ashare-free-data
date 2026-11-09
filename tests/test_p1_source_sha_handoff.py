import copy
import json
import tempfile
import unittest
from pathlib import Path
from collector.p1_partial_sha_copy_plan import plan
from collector.p1_source_sha_handoff import build
from tests.test_p1_partial_sha_copy_plan import build_epoch

ACTIVE="a"*64
OLD="b"*64


def readiness():
    return {
        "phase":"P1_MIGRATION_SOURCE_ARCHIVE_READINESS",
        "source_epoch_sha256":ACTIVE,
        "status":"CHECKPOINT_SOURCE_ORIGINALS_PRESENT_SHA_VERIFIED",
        "all_checkpoint_originals_durably_located":True,
        "archive_status_matches_epoch":True,
        "missing_or_invalid_shard_count":0,
        "verified_original_shards":2,"checkpoint_completed_shards":2,
        "verified_original_csv_files":2,"checkpoint_completed_issuers":2,
        "writer_cutover_authorized":False,"destination_mirror_verified":False,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],
    }


def gaps():
    return {
        "phase":"P1_LEGACY_ORIGINAL_RECEIPT_GAP_AUDIT",
        "active_source_sha256":ACTIVE,
        "trade_gate":"BLOCKED","orders":[],
        "writer_cutover_authorized":False,
        "destination_mirror_verified":False,
        "missing_receipts_synthesized":False,
        "missing_receipts_total":1,
        "missing_original_receipts":[{
            "source_epoch_prefix":OLD[:16],
            "shard_id":"shard_0001",
            "reason":"ORIGINAL_QUALITY_RECEIPT_MISSING_NOT_RECONSTRUCTIBLE"}],
    }


class SourceHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        build_epoch(self.root,ACTIVE)
        build_epoch(self.root,OLD,missing=(1,))
        self.partial=plan(self.root,ACTIVE)
        self.ready=readiness()
        self.gaps=gaps()

    def test_canonical_handoff_sha_and_no_trades_or_migration(self):
        result=build(self.partial,self.ready,self.gaps)
        self.assertEqual(result["eligible_shards"],3)
        self.assertEqual(result["eligible_original_files"],6)
        self.assertEqual(result["quarantined_source_shards"],1)
        self.assertEqual(result["active_verified_shards"],2)
        self.assertEqual(result["active_verified_csv_issuers"],2)
        self.assertEqual(len(result["source_file_inventory_sha256"]),64)
        self.assertEqual(sorted(x["path"] for x in result["original_paths_and_sha256"]),
                         [x["path"] for x in result["original_paths_and_sha256"]])
        self.assertFalse(result["destination_files_verified"])
        self.assertFalse(result["migration_performed"])
        self.assertFalse(result["automatic_copy_authorized"])
        self.assertFalse(result["writer_cutover_authorized"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertEqual(result["executable_candidates"],[])
        self.assertTrue(result["source_manifest_has_no_archive_status_files"])
        self.assertTrue(all("archive_status" not in row["path"]
                            for row in result["original_paths_and_sha256"]))
        self.assertEqual(result["source_file_inventory_sha256"],
                         build(self.partial,self.ready,self.gaps)["source_file_inventory_sha256"])

    def test_rejects_forged_or_incomplete_checkpoint_readiness(self):
        for key,value in (
            ("verified_original_shards",1),
            ("verified_original_csv_files",1),
            ("source_epoch_sha256","c"*64),
            ("destination_mirror_verified",True),
            ("writer_cutover_authorized",True),
            ("historical_PIT_verified",True),
            ("trade_gate","OPEN"),
            ("status","CHECKPOINT_ORIGINALS_INCOMPLETE_NO_CUTOVER"),
        ):
            bad=copy.deepcopy(self.ready);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                build(self.partial,bad,self.gaps)

    def test_rejects_missing_gap_and_current_epoch_quarantine(self):
        changed=copy.deepcopy(self.gaps)
        changed["missing_original_receipts"][0]["shard_id"]="shard_0000"
        with self.assertRaises(ValueError):
            build(self.partial,self.ready,changed)
        changed=copy.deepcopy(self.partial)
        changed["quarantine"][0]["source_epoch_prefix"]=ACTIVE[:16]
        with self.assertRaises(ValueError):
            build(changed,self.ready,self.gaps)

    def test_duplicate_or_tampered_file_sha_cannot_pass_handoff(self):
        changed=copy.deepcopy(self.partial)
        files=changed["eligible_source_shards"][0]["source_file_sha256"]
        files[1]["path"]=files[0]["path"]
        with self.assertRaises(ValueError):
            build(changed,self.ready,self.gaps)
        changed=copy.deepcopy(self.partial)
        changed["eligible_source_shards"][0]["source_file_sha256"][0]["sha256"]="NOT-A-SHA"
        with self.assertRaises(ValueError):
            build(changed,self.ready,self.gaps)

    def test_source_inventory_sha_changes_if_original_digest_changes(self):
        before=build(self.partial,self.ready,self.gaps)["source_file_inventory_sha256"]
        changed=copy.deepcopy(self.partial)
        changed["eligible_source_shards"][0]["source_file_sha256"][0]["sha256"]="d"*64
        after=build(changed,self.ready,self.gaps)["source_file_inventory_sha256"]
        self.assertNotEqual(before,after)
        # This report is only a checksum of the separately replayed plan;
        # it MUST NOT be misrepresented as a fresh source byte replay.

if __name__=="__main__":
    unittest.main()
