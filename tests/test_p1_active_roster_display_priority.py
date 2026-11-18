"""Source-of-truth regressions; no network, archive writes or trade actions."""
import copy
import json
import unittest
from pathlib import Path
from collector.p1_active_roster_display_priority import reconcile
from collector.p1_checkpoint import epoch_path

ROOT = Path(__file__).resolve().parents[1]


class ActiveP1SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads((ROOT/"evidence/p1_active_roster.json").read_text())
        cls.current = json.loads((ROOT/epoch_path(cls.lock["source_sha256"])).read_text())
        cls.old = json.loads((ROOT/"evidence/p1_checkpoint.json").read_text())

    def test_current_epoch_wins_and_never_sums_alias(self):
        result = reconcile(self.lock,self.current,self.old)
        self.assertEqual(result["active"]["source_sha256"],self.lock["source_sha256"])
        self.assertEqual(result["active"]["completed_shards"],self.current["completed_shards"])
        self.assertEqual(result["legacy_alias"]["completed_shards"],self.old["completed_shards"])
        self.assertFalse(result["alias_replaces_active_source"])
        self.assertFalse(result["cross_epoch_counts_addable"])
        self.assertIsNone(result["overall_P1_project_completion_pct"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertEqual(result["executable_candidates"],[])

    def test_legacy_substituted_for_active_rejected(self):
        with self.assertRaises(ValueError):
            reconcile(self.lock,self.old,self.current)

    def test_corrupt_active_checkpoint_rejected(self):
        broken=copy.deepcopy(self.current)
        broken["completed_shards"]+=1
        with self.assertRaises(ValueError):
            reconcile(self.lock,broken,self.old)

    def test_corrupt_active_roster_digest_rejected(self):
        broken=copy.deepcopy(self.lock)
        broken["source_sha256"]="0"*64
        with self.assertRaises((ValueError,KeyError)):
            reconcile(broken,self.current,self.old)

    def test_without_legacy_alias_active_survives(self):
        result=reconcile(self.lock,self.current)
        self.assertIsNone(result["legacy_alias"])
        self.assertEqual(result["active"]["completed_shards"],self.current["completed_shards"])

    def test_corrupt_legacy_not_silently_accepted(self):
        broken=copy.deepcopy(self.old)
        broken["completed_shards"]+=1
        with self.assertRaises(ValueError):
            reconcile(self.lock,self.current,broken)


if __name__=="__main__":
    unittest.main()
