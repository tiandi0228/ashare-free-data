import copy
import unittest
from collector.p234_evidence_metrics import assess

RUNS={"P2":42180658907,"P3":42180658939,"P4":42180658923}
def sample():
    p2={"phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,"orders":[],
        "feature_complete_shards":158,
        "observed_with_feature_gaps_shards":9,"observed_archived_shards":167,
        "unobserved_archived_shards":0,"full_archive_evidence_accounted":True,
        "full_archive_feature_coverage":False,
        "feature_issuer_count":1327,"issuer_evidence_gap_count":9,
        "observed_feature_or_gap_issuers":1336,"unobserved_issuer_count":0}
    p3={"phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,"orders":[],
        "deduplicated_research_text_pairs":38,
        "unpaired_halt_sources_remaining_in_bounded_research":25,
        "official_halt_resume_intervals_certified":0,
        "authenticated_first_publication_count":0,
        "text_only_halt_resume_pairs":[{} for _ in range(38)],
        "unpaired_original_halt_followups":[{} for _ in range(25)]}
    p4={"status":"MODELLED_FEE_BARRIER_GAP_EXPLAINED_NO_BACKTEST",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,"orders":[],
        "source_verified_price_pairs":15161,
        "source_frozen_5pct_reward_risk_passes":0,
        "gross_2to1_erased_by_modelled_friction":14816,
        "trade_authorized":False,"historical_OOS_validated":False,
        "broker_trades_verified":0}
    return p2,p3,p4

class ScorecardTests(unittest.TestCase):
    def test_exact_run_bound_denominators(self):
        r=assess(*sample(),RUNS)
        self.assertEqual(r["P2"]["feature_coverage_pct"],94.61)
        self.assertEqual(r["P3"]["unpaired_halt_sources"],25)
        self.assertEqual(r["P4"]["source_proxy_price_pairs"],15161)
        self.assertEqual(r["P4"]["frozen_5pct_reward_risk_passes"],0)
        self.assertIsNone(r["actual_overall_project_progress_pct"])
        self.assertEqual(r["engineering_baseline_pct_not_recomputed"],{"P2":30,"P3":30,"P4":50})
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["buy_recommendations_authorized"])

    def test_invalid_run_identity_rejected(self):
        for ids in ({"P2":1,"P3":1,"P4":2},{"P2":0,"P3":2,"P4":3},
                    {"P2":1,"P3":2}):
            with self.assertRaises(ValueError):assess(*sample(),ids)

    def test_inconsistent_or_untrusted_sources_fail_closed(self):
        for index,field,value in [
            (0,"observed_archived_shards",166),
            (0,"full_archive_evidence_accounted",False),
            (0,"feature_complete_shards",True),
            (1,"official_halt_resume_intervals_certified",1),
            (1,"unpaired_halt_sources_remaining_in_bounded_research",24),
            (2,"source_frozen_5pct_reward_risk_passes",15162),
            (2,"broker_trades_verified",1),
            (2,"trade_authorized",True),
            (2,"status","SYNTHETIC_BACKTEST_CERTIFIED"),
        ]:
            with self.subTest(index=index,field=field):
                records=copy.deepcopy(sample())
                records[index][field]=value
                with self.assertRaises(ValueError):
                    assess(*records,RUNS)

    def test_missing_data_never_uses_stale_numbers(self):
        records=sample()
        del records[0]["feature_complete_shards"]
        with self.assertRaises(ValueError):assess(*records,RUNS)

if __name__=="__main__":unittest.main()
