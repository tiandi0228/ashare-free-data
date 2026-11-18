"""Real archived P2 scored sample must never bypass historical issuer ST veto."""
import copy
import unittest
from collector.p4_real_archived_ranking_st_join import integrate,EPOCH
from collector.p3_four_issuer_st_crosswalk import reconcile
from tests.test_p3_four_issuer_st_crosswalk import inputs
from tests.test_p2_real_archive_research_screen import fixture

def sample():
    source,risk=inputs()
    crosswalk=reconcile(source,risk)
    page=fixture()
    page["source_epoch_sha256"]=EPOCH
    page["selected_shards"]=["shard_0033"]
    page["evidence_gaps"]=[{"issuer":"sh.600363",
      "reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"}]
    return page,crosswalk,source

class RealRankedSTJoinTests(unittest.TestCase):
    def setUp(self):
        self.page,self.crosswalk,self.triage=sample()

    def fail(self):
        with self.assertRaises(ValueError):
            integrate(self.page,self.crosswalk,self.triage)

    def test_descriptive_originals_and_st_gap_blocked(self):
        r=integrate(self.page,self.crosswalk,self.triage)
        self.assertEqual(r["descriptive_ranked_original_issuers"],2)
        self.assertEqual(r["source_feature_gap_issuers"],1)
        self.assertTrue(r["st_600363_source_gap_held_out_of_ranking"])
        self.assertTrue(r["st_600363_dated_veto_verified_in_research"])
        self.assertEqual(r["other_issuer_PIT_unknown_rejected"],2)
        self.assertEqual(r["candidate_approvals"],0)
        self.assertFalse(r["production_candidate_pipeline_integrated"])
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_wrong_epoch(self):
        self.page["source_epoch_sha256"]="a"*64
        self.fail()

    def test_wrong_asof(self):
        self.page["asof_completed_day"]="2026-10-19"
        self.fail()

    def test_missing_st_shard(self):
        self.page["selected_shards"]=["shard_0001"]
        self.fail()

    def test_missing_st_gap(self):
        self.page["evidence_gaps"][0]["issuer"]="sh.600999"
        self.fail()

    def test_ranking_forged_st_feature(self):
        self.page["features"][0]["issuer"]="sh.600363"
        self.fail()

    def test_unsafe_buy_signal(self):
        self.page["features"][0]["buy_signal"]=True
        self.fail()

    def test_drifted_st_original_sha(self):
        next(x for x in self.triage["research_actions"]
             if x["issuer"]=="sh.600363")["original_csv_sha256"]="a"*64
        self.fail()

    def test_open_trading_gate(self):
        self.crosswalk["trade_gate"]="OPEN"
        self.fail()

    def test_forced_pit(self):
        self.page["historical_PIT_verified"]=True
        self.fail()

    def test_over_100_ranked_issuers_chunked_without_drops(self):
        features=self.page["features"]
        generated=[]
        for i in range(111):
            item=copy.deepcopy(features[i%2])
            item["issuer"]=f"sh.{601000+i:06d}"
            item["source_original_sha256"]=f"{i+1:064x}"
            generated.append(item)
        self.page["features"]=generated
        self.page["scoped_verified_issuers"]=112
        self.page["computed_feature_issuers"]=111
        self.page["missing_feature_evidence_issuers"]=1
        r=integrate(self.page,self.crosswalk,self.triage)
        self.assertEqual(r["descriptive_ranked_original_issuers"],111)
        self.assertEqual(len(r["real_original_candidate_rows"]),111)
        self.assertEqual(r["candidate_approvals"],0)
