import copy
import unittest
from collector.p2_real_archive_research_screen import screen
from collector.p4_dual_horizon_receipt_gate import inspect
from collector.p4_dual_horizon_real_evidence_join import join
from tests.test_p2_real_archive_research_screen import fixture


def inputs():
    raw = fixture()
    raw["asof_completed_day"] = "2026-10-20"
    p2 = screen(raw)
    p4 = inspect({"asof": "2026-11-10", "symbols": [
        {"issuer": "sh.600000", "receipts": []},
        {"issuer": "sz.002249", "receipts": []},
        {"issuer": "sh.600001", "receipts": []},
    ]})
    return p2, p4


class RealEvidenceJoinTests(unittest.TestCase):
    def test_real_archived_p2_prices_are_not_short_or_medium_buy_signals(self):
        p2,p4=inputs()
        r=join(p2,p4,"2026-11-10")
        self.assertEqual(r["p2_scoped_issuer_count"],3)
        self.assertEqual(r["p2_descriptive_rows"],2)
        self.assertEqual(r["p2_missing_feature_issuer_count"],1)
        self.assertEqual(r["p4_unmatched_receipt_issuers"],["sh.600001"])
        self.assertEqual(r["status"],"ARCHIVED_DESCRIPTIVE_EVIDENCE_NOT_ACTIONABLE")
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertFalse(r["buy_recommendations_authorized"])
        for x in r["symbols"]:
            self.assertEqual(x["category"],"D_NO_VERIFIED_BUY_THESIS")
            self.assertEqual(x["archived_observation_age_days"],21)
            self.assertFalse(x["archived_quote_is_current"])
            self.assertIn("sector_leadership_confirmed",
                          x["short_horizon"]["required_independent_proofs"])
            self.assertIn("valuation_margin_confirmed",
                          x["medium_horizon"]["required_independent_proofs"])

    def test_forged_p2_research_trade_claim_rejected(self):
        p2,p4=inputs()
        for key,value in (("trade_gate","OPEN"),("orders",[{"BUY":1}]),
                          ("historical_PIT_verified",True),
                          ("complete_mainboard_coverage",True),
                          ("archive_commit_sha","main")):
            bad=copy.deepcopy(p2)
            bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                join(bad,p4,"2026-11-10")
        bad=copy.deepcopy(p2)
        bad["descriptive_order"][0]["buy_signal"]=True
        with self.assertRaises(ValueError):
            join(bad,p4,"2026-11-10")

    def test_untrusted_p4_receipts_and_bad_date_rejected(self):
        p2,p4=inputs()
        bad=copy.deepcopy(p4)
        bad["source_authenticity_verified"]=True
        with self.assertRaises(ValueError):
            join(p2,bad,"2026-11-10")
        with self.assertRaises(ValueError):
            join(p2,p4,"2026-10-19")
        with self.assertRaises(ValueError):
            join(p2,p4,"2026-11-11")

    def test_p4_unrelated_observation_never_implies_coverage(self):
        p2,p4=inputs()
        p4=inspect({"asof":"2026-11-10","symbols":[
            {"issuer":"sz.000069","receipts":[]},
        ]})
        r=join(p2,p4,"2026-11-10")
        self.assertEqual(r["p4_unmatched_receipt_issuers"],["sz.000069"])
        self.assertFalse(r["all_market_coverage_verified"])
        self.assertTrue(all(x["short_horizon"]["provisional_receipt_state"] is None
                            for x in r["symbols"]))

    def test_tampered_counts_price_or_non_mainboard_fail_closed(self):
        p2,p4=inputs()
        for field,value in (("ranked_observations",99),("source_gap_count",0)):
            bad=copy.deepcopy(p2)
            bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                join(bad,p4,"2026-11-10")
        for field,value in (("last_close_cny","NaN"),
                            ("volume_vs_prior20_ratio","-1"),
                            ("issuer","sz.300015"),
                            ("source_original_sha256","broken")):
            bad=copy.deepcopy(p2)
            bad["descriptive_order"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                join(bad,p4,"2026-11-10")

    def test_two_horizons_are_independent_and_evidence_gaps_persist(self):
        p2,p4=inputs()
        p4["provisional_assertion_only_assessment"]["symbols"][0]["short"]["state"]="RESEARCH_FIT_NOT_ACTIONABLE"
        p4["provisional_assertion_only_assessment"]["symbols"][0]["medium"]["state"]="RESEARCH_FIT_NOT_ACTIONABLE"
        r=join(p2,p4,"2026-11-10")
        x=next(i for i in r["symbols"] if i["issuer"]=="sh.600000")
        self.assertEqual(x["short_horizon"]["provisional_receipt_state"],"RESEARCH_FIT_NOT_ACTIONABLE")
        self.assertEqual(x["medium_horizon"]["provisional_receipt_state"],"RESEARCH_FIT_NOT_ACTIONABLE")
        self.assertEqual(x["category"],"D_NO_VERIFIED_BUY_THESIS")
        self.assertFalse(r["source_claims_authenticated"])


if __name__=="__main__":
    unittest.main()
