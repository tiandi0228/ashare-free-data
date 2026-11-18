"""P4 dual-horizon category cannot bypass real issuer-notice risk research gate."""
import copy
import json
import unittest
from pathlib import Path
from collector.p4_historical_st_dual_horizon_integration import integrate
from collector.p4_dual_horizon_research import assess
from collector.p3_four_issuer_st_crosswalk import reconcile
from tests.test_p3_four_issuer_st_crosswalk import inputs

EVIDENCE = Path(__file__).resolve().parents[1]/"evidence/p4_synthetic_dual_horizon_st_adversarial.json"

def sample():
    risk, sources=inputs()
    crosswalk=reconcile(risk,sources)
    observed=[
        {"issuer":"sh.600363","signal_known_after_close_date":"2026-09-30",
         "research_only":True,"buy_signal":False},
        {"issuer":"sh.600825","signal_known_after_close_date":"2026-09-30",
         "research_only":True,"buy_signal":False},
    ]
    research=json.loads(EVIDENCE.read_text())
    return crosswalk,research,observed

class P4DualHorizonSTIntegration(unittest.TestCase):
    def setUp(self):
        self.crosswalk,self.research,self.observed=sample()

    def reject(self):
        with self.assertRaises(ValueError):
            integrate(self.crosswalk,self.research,self.observed)

    def test_optimistic_upstream_categories_overridden_by_st_and_unknown_pit(self):
        upstream=assess(self.research)
        self.assertEqual([x["category"] for x in upstream["symbols"]],
                         ["C_DUAL_HORIZON_RESEARCH_ONLY"]*2)
        result=integrate(self.crosswalk,self.research,self.observed)
        self.assertEqual(result["assessed_issuers"],2)
        self.assertEqual(result["dated_issuer_notice_veto_count"],1)
        self.assertEqual(result["research_labels_safety_blocked"],2)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertEqual(result["executable_candidates"],[])
        self.assertFalse(result["production_candidate_pipeline_integrated"])
        self.assertTrue(result["all_research_candidates_blocked"])
        self.assertEqual(result["results"][0]["historical_risk_state"],
                         "VETO_ISSUER_NOTICE_ST_EFFECTIVE")
        self.assertEqual(result["results"][1]["historical_risk_state"],
                         "UNKNOWN_PIT_STATUS_FAIL_CLOSED")
        self.assertTrue(all(x["final_research_candidate_category"]==
            "D_BLOCKED_HISTORICAL_ST_HALT_OR_UNKNOWN_PIT" for x in result["results"]))

    def test_reject_wrong_asof_day(self):
        self.research["asof"]="2026-09-29"
        self.reject()

    def test_reject_mixed_asof_days(self):
        self.observed[1]["signal_known_after_close_date"]="2026-10-01"
        self.reject()

    def test_reject_mismatched_issuer_set(self):
        self.observed[1]["issuer"]="sh.600301"
        self.reject()

    def test_reject_unapproved_buy_signal(self):
        self.observed[0]["buy_signal"]=True
        self.reject()

    def test_reject_source_pit_promotion(self):
        self.crosswalk["historical_PIT_verified"]=True
        self.reject()

    def test_reject_source_open_gate(self):
        self.crosswalk["trade_gate"]="OPEN"
        self.reject()

    def test_reject_missing_research_issuer(self):
        self.research["symbols"].pop()
        self.reject()

    def test_reject_duplicate_asof_issuer(self):
        self.observed[1]["issuer"]="sh.600363"
        self.reject()

    def test_reject_weekend_replay(self):
        self.research["asof"]="2026-10-03"
        self.observed[0]["signal_known_after_close_date"]="2026-10-03"
        self.observed[1]["signal_known_after_close_date"]="2026-10-03"
        self.reject()

    def test_upstream_research_claims_cannot_emit_orders(self):
        self.research["symbols"][0]["short"]["fresh_executable_quotes"]=True
        result=integrate(self.crosswalk,self.research,self.observed)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertFalse(result["buy_recommendations_authorized"])

    def test_no_lookahead_promotions(self):
        self.research["symbols"][0]["universe_guard"]["published_on"]="2026-10-01"
        result=integrate(self.crosswalk,self.research,self.observed)
        self.assertEqual(result["results"][0]["historical_risk_state"],
                         "VETO_ISSUER_NOTICE_ST_EFFECTIVE")
        self.assertEqual(result["results"][0]["final_research_candidate_category"],
                         "D_BLOCKED_HISTORICAL_ST_HALT_OR_UNKNOWN_PIT")
