import copy
import unittest
from collector.p234_evidence_scoreboard import scoreboard

def fixtures():
    p2={"phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "orders":[],"executable_candidates":[],
        "observed_archived_shards":167,"feature_complete_shards":158,
        "observed_with_feature_gaps_shards":9,"unobserved_archived_shards":0,
        "checkpoint_completed_shards":167,"observed_feature_or_gap_issuers":1336,
        "feature_issuer_count":1327,"issuer_evidence_gap_count":9,
        "unobserved_issuer_count":0,
        "full_archive_evidence_accounted":True,
        "full_archive_feature_coverage":False}
    p3={"phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "orders":[],"executable_candidates":[],
        "authenticated_first_publication_count":0,
        "official_halt_resume_intervals_certified":0,
        "deduplicated_research_text_pairs":38,
        "unpaired_halt_sources_remaining_in_bounded_research":25,
        "unique_resume_pdf_originals_replayed":39,
        "archived_resume_runs_replayed":183,
        "text_only_halt_resume_pairs":[{} for _ in range(38)],
        "unpaired_original_halt_followups":[{} for _ in range(25)]}
    p4={"phase":"P4_FROZEN_STOP_TARGET_FEE_FLOOR_EXPLANATION",
        "status":"MODELLED_FEE_BARRIER_GAP_EXPLAINED_NO_BACKTEST",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "historical_OOS_validated":False,"strategy_backtest_certified":False,
        "orders":[],"executable_candidates":[],
        "source_verified_price_pairs":15161,"cash_eligible_observation_pairs":14816,
        "source_frozen_5pct_reward_risk_passes":0,
        "gross_2to1_erased_by_modelled_friction":14816}
    return p2,p3,p4

class TestEvidenceScoreboard(unittest.TestCase):
    def test_reconciled_research_metrics_not_invented_engineering_percent(self):
        r=scoreboard(*fixtures(),{"p2":11,"p3":12,"p4":13})
        self.assertEqual(r["p2"]["research_feature_coverage_pct"],94.61)
        self.assertEqual(r["p3"]["certified_tradability_intervals"],0)
        self.assertEqual(r["p4"]["frozen_target_net_2to1_model_passes"],0)
        self.assertIsNone(r["engineering_completion_pct"]["p2"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])

    def test_fail_closed_for_inconsistent_or_forged_results(self):
        base=fixtures()
        for key,val in (("feature_complete_shards",167),
                        ("unobserved_archived_shards",1)):
            p=list(copy.deepcopy(base))
            p[0][key]=val
            with self.assertRaises(ValueError):scoreboard(*p,{"p2":11,"p3":12,"p4":13})
        p=list(copy.deepcopy(base));p[1]["authenticated_first_publication_count"]=1
        with self.assertRaises(ValueError):scoreboard(*p,{"p2":11,"p3":12,"p4":13})
        p=list(copy.deepcopy(base));p[2]["source_frozen_5pct_reward_risk_passes"]=20000
        with self.assertRaises(ValueError):scoreboard(*p,{"p2":11,"p3":12,"p4":13})
        p=list(copy.deepcopy(base));p[2]["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):scoreboard(*p,{"p2":11,"p3":12,"p4":13})


    def test_reject_duplicate_run_ids_or_boolean_run_id(self):
        p2,p3,p4=fixtures()
        for ids in (
            {"p2":11,"p3":11,"p4":13},
            {"p2":11,"p3":12,"p4":True},
        ):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                scoreboard(p2,p3,p4,ids)

    def test_reject_overlapping_modelled_passes_and_erased_pairs(self):
        p2,p3,p4=fixtures()
        p4["source_frozen_5pct_reward_risk_passes"]=1
        # All cash-eligible pairs have already been counted as erased by fees;
        # a new pass would double count at least one observation.
        with self.assertRaises(ValueError):
            scoreboard(p2,p3,p4,{"p2":11,"p3":12,"p4":13})

    def test_reject_nonlist_p3_evidence_with_clear_error(self):
        p2,p3,p4=fixtures()
        p3["text_only_halt_resume_pairs"]=None
        with self.assertRaisesRegex(ValueError,"unreconciled P3"):
            scoreboard(p2,p3,p4,{"p2":11,"p3":12,"p4":13})

if __name__=="__main__":
    unittest.main()
