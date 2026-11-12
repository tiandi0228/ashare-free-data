"""P1 manual-gap remote readback tests. All GitHub responses are mocked."""
import base64
import copy
import json
import unittest

from collector.p1_gap_remote_preflight import decode_contents, read_remote, verify
from tests.test_p1_prewrite_gap_guard import fixtures


class RemoteGapPreflightTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.prior, self.archive = fixtures()
        self.selection = {"phase": "P1_BOUNDED_PILOT_SELECTION",
                          "requested_shards": 2, "selected_shards": [5, 6],
                          "selected_count": 2, "trade_gate": "BLOCKED", "orders": []}

    def mock_fetch(self, repo, path, ref):
        self.assertEqual(repo, "tiandi0228/ashare-free-data")
        if ref == "main":
            self.assertEqual(path, "evidence/checkpoints/"+"a"*64+".json")
            return self.prior
        self.assertEqual(ref, "research-csv-archive")
        self.assertEqual(path, "a"*16+"/archive_status.json")
        return self.archive

    def test_two_remote_rechecks_success_but_no_write_permission(self):
        result = verify(self.plan,self.selection,self.prior,"tiandi0228/ashare-free-data",self.mock_fetch)
        self.assertEqual(result["selected_missing_shards"],[5,6])
        self.assertTrue(result["remote_main_checkpoint_read_in_this_attempt"])
        self.assertTrue(result["remote_archive_status_read_in_this_attempt"])
        self.assertFalse(result["permission_to_write_or_trade"])
        self.assertEqual(result["orders"],[])
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_after_selection_checkpoint_progress_rejected(self):
        newer=copy.deepcopy(self.prior)
        newer["completed"].append({"index":5,"issuer_count":1,
                    "manifest_sha256":f"{6:064x}","receipt_sha256":f"{105:064x}"})
        newer["completed_shards"]=6;newer["completed_issuers"]=6
        newer["pending_shards"]=[6];newer["next_shard"]=6
        def fetch(repo,path,ref):
            return newer if ref=="main" else self.archive
        with self.assertRaises(ValueError):
            verify(self.plan,self.selection,self.prior,"tiandi0228/ashare-free-data",fetch)

    def test_changed_archive_index_rejected(self):
        archived=copy.deepcopy(self.archive);archived["archived_shards"].append(5)
        def fetch(repo,path,ref):
            return self.prior if ref=="main" else archived
        with self.assertRaises(ValueError):
            verify(self.plan,self.selection,self.prior,"tiandi0228/ashare-free-data",fetch)

    def test_unapproved_selection_fails_before_network(self):
        self.selection["trade_gate"]="OPEN"
        def unexpected(*args):
            self.fail("must not issue network request for unsafe selection")
        with self.assertRaises(ValueError):
            verify(self.plan,self.selection,self.prior,"tiandi0228/ashare-free-data",unexpected)

    def test_mismatched_selected_count_rejected(self):
        self.selection["selected_count"]=1
        with self.assertRaises(ValueError):
            verify(self.plan,self.selection,self.prior,"tiandi0228/ashare-free-data",self.mock_fetch)

    def test_valid_json_contents_envelope(self):
        record={"trade_gate":"BLOCKED"}
        raw=base64.b64encode(json.dumps(record).encode()).decode()
        self.assertEqual(decode_contents({"encoding":"base64","content":raw}),record)

    def test_corrupted_base64_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_contents({"encoding":"base64","content":"bad!!!"})

    def test_missing_encoding_denied(self):
        with self.assertRaises(ValueError):
            decode_contents({"content":"e30="})

    def test_non_whitelisted_remote_ref_denied_before_call(self):
        with self.assertRaises(ValueError):
            read_remote("tiandi0228/ashare-free-data","archive_status.json","untrusted-branch")

    def test_invalid_repository_denied_before_call(self):
        with self.assertRaises(ValueError):
            read_remote("../injection","archive_status.json","main")


if __name__ == "__main__":
    unittest.main()
