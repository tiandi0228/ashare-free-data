import unittest
from collector.p1_optional_second import decide
from collector.p1_run_progress import assess
from collector.p1_shard_ledger import reconcile


class P1RunProgressTests(unittest.TestCase):
    def fixture(self):
        source="a"*64
        plan={"phase":"P1_FRESH_VENDOR_SHARD_PLAN","trade_gate":"BLOCKED",
              "source_sha256":source,"shard_count":2,
              "shards":[{"index":0,"sha256":"b"*64,"count":1},
                        {"index":1,"sha256":"c"*64,"count":1}]}
        def receipt(index):
            return {"manifest_sha256":plan["shards"][index]["sha256"],
                    "issuer_count":1,"status":"OBSERVED_SUBSET_UNVERIFIED",
                    "trade_gate":"BLOCKED","paid_api_calls":0,"query_attempts":1,
                    "results":[{"code":f"sh.60000{index}","status":"OBSERVED_UNVERIFIED",
                                "sha256":"d"*64}]}
        prior=reconcile(plan,[(0,receipt(0))])
        current=reconcile(plan,[(1,receipt(1))],prior)
        audit={"source_sha256":source,"trade_gate":"BLOCKED",
               "historical_PIT_verified":False,"ledger_issuers":2,
               "archived_issuers":2,"archive_gap_issuers":0,
               "archive_csv_replay_enabled":True,
               "independently_replayed_active_rows":2,
               "independently_replayed_suspended_rows":0}
        selection={"selected_shards":[1],"selected_count":1,"trade_gate":"BLOCKED"}
        policy=decide("false","skipped","NONE")
        return plan,prior,current,audit,selection,policy

    def test_confirmed_durable_increment_in_same_epoch(self):
        p,prior,current,audit,selection,policy=self.fixture()
        result=assess(p,current,audit,selection,policy,prior)
        self.assertEqual(result["status"],"DURABLE_PROGRESS")
        self.assertEqual(result["previous_shards"],1)
        self.assertEqual(result["current_shards"],2)
        self.assertEqual(result["new_selected_shards"],[1])
        self.assertEqual(result["new_shards_durably_accepted"],1)
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_green_no_progress_is_explicit(self):
        p,prior,current,audit,selection,policy=self.fixture()
        audit["ledger_issuers"]=1
        audit["archived_issuers"]=1
        result=assess(p,prior,audit,selection,policy,prior)
        self.assertEqual(result["status"],"SUCCESS_NO_NEW_SHARD")
        self.assertEqual(result["new_shard_count"],0)
        self.assertEqual(result["new_shards_durably_accepted"],0)

    def test_archive_gap_not_claimed_as_durable_growth(self):
        p,prior,current,audit,selection,policy=self.fixture()
        audit["archived_issuers"]=1
        audit["archive_gap_issuers"]=1
        report=assess(p,current,audit,selection,policy,prior)
        self.assertEqual(report["status"],"ARCHIVE_GAP")
        self.assertEqual(report["new_shards_durably_accepted"],0)

    def test_two_verified_shards_are_acceptable(self):
        p,prior,current,audit,selection,policy=self.fixture()
        selection.update(selected_shards=[0,1],selected_count=2)
        policy=decide("true","success","0001")
        result=assess(p,current,audit,selection,policy,None)
        self.assertEqual(result["new_selected_shards"],[0,1])
        self.assertEqual(result["new_shards_durably_accepted"],2)

    def test_cross_epoch_and_unselected_growth_rejected(self):
        p,prior,current,audit,selection,policy=self.fixture()
        mismatch=dict(prior,source_sha256="f"*64)
        with self.assertRaisesRegex(ValueError,"cross-epoch"):
            assess(p,current,audit,selection,policy,mismatch)
        selection["selected_shards"]=[0]
        with self.assertRaisesRegex(ValueError,"not selected"):
            assess(p,current,audit,selection,policy,prior)

    def test_progress_regression_and_receipt_mutation_rejected(self):
        p,prior,current,audit,selection,policy=self.fixture()
        prior_archive=dict(audit,ledger_issuers=1,archived_issuers=1)
        with self.assertRaisesRegex(ValueError,"regression"):
            assess(p,prior,prior_archive,selection,policy,current)
        altered=dict(current)
        altered["completed"]=[dict(x) for x in current["completed"]]
        altered["completed"][0]["receipt_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"replaced receipt"):
            assess(p,altered,audit,selection,policy,prior)

    def test_unreplayed_archive_cannot_be_called_durable(self):
        p,prior,current,audit,selection,policy=self.fixture()
        shallow=dict(audit,archive_csv_replay_enabled=False)
        with self.assertRaisesRegex(ValueError,"archive audit"):
            assess(p,current,shallow,selection,policy,prior)
        forged=dict(audit,independently_replayed_active_rows=0,
                    independently_replayed_suspended_rows=0)
        with self.assertRaisesRegex(ValueError,"replay counters"):
            assess(p,current,forged,selection,policy,prior)

    def test_malformed_archive_counters_or_policy_rejected(self):
        p,prior,current,audit,selection,policy=self.fixture()
        broken=dict(audit,archive_gap_issuers=2)
        with self.assertRaisesRegex(ValueError,"coverage"):
            assess(p,current,broken,selection,policy,prior)
        invalid=dict(policy,trade_gate="OPEN")
        with self.assertRaisesRegex(ValueError,"acceptance"):
            assess(p,current,audit,selection,invalid,prior)


if __name__ == "__main__":
    unittest.main()
