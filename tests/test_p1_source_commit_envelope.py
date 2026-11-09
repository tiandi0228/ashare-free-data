import copy
import tempfile
import unittest
from pathlib import Path

from collector.p1_partial_sha_copy_plan import plan
from collector.p1_source_sha_handoff import build
from collector.p1_source_handoff_independent_replay import replay
from collector.p1_source_commit_envelope import seal
from tests.test_p1_source_sha_handoff import ACTIVE,OLD,readiness,gaps
from tests.test_p1_partial_sha_copy_plan import build_epoch

SOURCE="a"*40
CODE="b"*40


class ImmutableCommitEnvelopeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        build_epoch(self.root,ACTIVE)
        build_epoch(self.root,OLD,missing=(1,))
        self.handoff=build(plan(self.root,ACTIVE),readiness(),gaps())
        self.replay=replay(self.root,self.handoff)

    def test_reconciled_source_commit_and_status_digests_no_target_claim(self):
        obj=seal(self.handoff,self.replay,SOURCE,CODE)
        self.assertEqual(obj["source_archive_commit_sha"],SOURCE)
        self.assertEqual(obj["execution_main_commit_sha"],CODE)
        self.assertEqual(obj["eligible_original_files"],6)
        self.assertEqual(len(obj["archive_status_original_sha256"]),2)
        self.assertEqual(obj["source_epoch_sha256"],ACTIVE)
        self.assertEqual(obj["source_handoff_envelope_sha256"],
                         seal(self.handoff,self.replay,SOURCE,CODE)["source_handoff_envelope_sha256"])
        self.assertFalse(obj["destination_files_verified"])
        self.assertFalse(obj["migration_performed"])
        self.assertFalse(obj["writer_cutover_authorized"])
        self.assertIsNone(obj["destination_commit_sha"])
        self.assertEqual(obj["trade_gate"],"BLOCKED")
        self.assertEqual(obj["orders"],[])

    def test_different_source_or_code_commit_changes_seal(self):
        original=seal(self.handoff,self.replay,SOURCE,CODE)["source_handoff_envelope_sha256"]
        self.assertNotEqual(original,
            seal(self.handoff,self.replay,"c"*40,CODE)["source_handoff_envelope_sha256"])
        self.assertNotEqual(original,
            seal(self.handoff,self.replay,SOURCE,"d"*40)["source_handoff_envelope_sha256"])

    def test_missing_or_invalid_commit_sha_rejected(self):
        for bad in ("", "0"*40, "A"*40, "g"*40, "a"*39, "a"*64):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                seal(self.handoff,self.replay,bad,CODE)

    def test_replay_source_epoch_sha_and_original_status_must_match(self):
        for key,value in (
            ("source_epoch_sha256","c"*64),
            ("source_file_inventory_sha256","d"*64),
            ("source_files_replayed",3),
            ("source_shards_replayed",1),
            ("destination_files_verified",True),
            ("trade_gate","OPEN"),
            ("migration_performed",True),
        ):
            bad=copy.deepcopy(self.replay);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                seal(self.handoff,bad,SOURCE,CODE)

    def test_missing_duplicate_or_invalid_archive_status_sha_rejected(self):
        for case in ("missing_active","duplicate","invalid_digest"):
            bad=copy.deepcopy(self.replay)
            rows=bad["archive_status_original_sha256"]
            if case=="missing_active":
                rows[:]=[r for r in rows if not r["path"].startswith(ACTIVE[:16])]
            elif case=="duplicate":
                rows.append(copy.deepcopy(rows[0]))
            else:
                rows[0]["sha256"]="broken"
            with self.subTest(case=case),self.assertRaises(ValueError):
                seal(self.handoff,bad,SOURCE,CODE)

    def test_handoff_cannot_be_promoted_to_migrated_status(self):
        for key,value in (
            ("destination_files_verified",True),
            ("writer_cutover_authorized",True),
            ("historical_PIT_verified",True),
            ("trade_gate","OPEN"),
            ("eligible_original_files",7),
        ):
            bad=copy.deepcopy(self.handoff);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                seal(bad,self.replay,SOURCE,CODE)


if __name__=="__main__":
    unittest.main()
