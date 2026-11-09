import copy
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_partial_sha_copy_plan import plan
from collector.p1_source_sha_handoff import build
from collector.p1_source_handoff_independent_replay import replay
from tests.test_p1_source_sha_handoff import ACTIVE,OLD,readiness,gaps
from tests.test_p1_partial_sha_copy_plan import build_epoch


class IndependentSourceHandoffReplayTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.active=build_epoch(self.root,ACTIVE)
        self.old=build_epoch(self.root,OLD,missing=(1,))
        self.handoff=build(plan(self.root,ACTIVE),readiness(),gaps())

    def test_independent_replay_and_legacy_quarantine(self):
        r=replay(self.root,self.handoff)
        self.assertEqual(r["source_shards_replayed"],3)
        self.assertEqual(r["source_files_replayed"],6)
        self.assertEqual(r["quarantined_original_shards"],
                         [OLD[:16]+"/shard_0001"])
        self.assertEqual(len(r["archive_status_original_sha256"]),2)
        self.assertEqual(r["source_file_inventory_sha256"],
                         self.handoff["source_file_inventory_sha256"])
        self.assertFalse(r["destination_files_verified"])
        self.assertFalse(r["migration_performed"])
        self.assertFalse(r["writer_cutover_authorized"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])

    def test_tampered_source_csv_or_receipt_is_rejected(self):
        csv=self.active/"shard_0000/sh_600000.csv"
        csv.write_text("changed after manifest creation")
        with self.assertRaisesRegex(ValueError,"changed after handoff"):
            replay(self.root,self.handoff)

    def test_missing_status_and_metadata_forgery_fail(self):
        path=self.old/"archive_status.json"
        content=path.read_text()
        path.unlink()
        with self.assertRaises(ValueError):
            replay(self.root,self.handoff)
        path.write_text(content)
        d=json.loads(content);d["trade_gate"]="OPEN"
        path.write_text(json.dumps(d))
        with self.assertRaises(ValueError):
            replay(self.root,self.handoff)

    def test_handoff_cannot_omit_original_or_invent_extra(self):
        missing=copy.deepcopy(self.handoff)
        missing["original_paths_and_sha256"].pop(0)
        # Even if an adversary updates the displayed count, the canonical
        # digest must independently reject the altered handoff.
        missing["eligible_original_files"]-=1
        with self.assertRaisesRegex(ValueError,"checksum mismatch"):
            replay(self.root,missing)
        extra=self.active/"shard_0000/extra.csv"
        extra.write_text("unexpected file")
        with self.assertRaisesRegex(ValueError,"file set differs"):
            replay(self.root,self.handoff)

    def test_quarantined_original_receipt_later_appearing_invalidates_handoff(self):
        (self.old/"shard_0001/quality.json").write_text("{}")
        with self.assertRaisesRegex(ValueError,"omitted a shard"):
            replay(self.root,self.handoff)

    def test_handoff_without_locked_gate_or_with_forged_destination_rejected(self):
        for key,value in (
            ("trade_gate","OPEN"),
            ("destination_files_verified",True),
            ("migration_performed",True),
            ("writer_cutover_authorized",True),
            ("historical_PIT_verified",True),
            ("source_file_inventory_sha256","0"*64),
        ):
            mutated=copy.deepcopy(self.handoff)
            mutated[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                replay(self.root,mutated)

    def test_source_replay_does_not_modify_original_directory(self):
        before=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        replay(self.root,self.handoff)
        after=sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
