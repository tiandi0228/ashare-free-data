import copy
import unittest

from collector.p4_dual_horizon_research import assess

SHORT = {
    "source": "https://example.org/short-confirmation",
    "published_on": "2026-11-09",
    "price_structure_confirmed": True,
    "relative_strength_confirmed": True,
    "sector_leadership_confirmed": True,
    "volume_expansion_confirmed": True,
    "fresh_material_catalyst_verified": True,
    "net_risk_reward_ratio": "2.10",
    "planned_net_portfolio_loss_fraction": "0.029",
}
MEDIUM = {
    "source": "https://example.org/official-earnings",
    "published_on": "2026-11-09",
    "fundamental_improvement_confirmed": True,
    "valuation_margin_confirmed": True,
    "medium_catalyst_confirmed": True,
    "financial_health_reviewed": True,
    "sector_cycle_confirmed": True,
    "stress_drawdown_fraction": "0.12",
    "debt_and_liquidity_risk_reviewed": True,
    "earnings_event_risk_reviewed": True,
    "fundamental_invalidation_defined": True,
}
GUARD = {
    "official_pit_mainboard_non_st_confirmed": True,
    "no_suspension_confirmed": True,
    "source": "https://example.org/official-st-halt-date",
    "published_on": "2026-11-09",
}


def input_for(short=None, medium=None, guard=None):
    return {
        "asof": "2026-11-10",
        "symbols": [{
            "issuer": "sz.000069",
            "universe_guard": copy.deepcopy(GUARD if guard is None else guard),
            "short": copy.deepcopy(SHORT if short is None else short),
            "medium": copy.deepcopy(MEDIUM if medium is None else medium),
        }],
    }


class DualHorizonResearchTests(unittest.TestCase):
    def test_both_horizons_separate_and_non_executable(self):
        result = assess(input_for())
        self.assertEqual(result["symbols"][0]["category"],
                         "C_DUAL_HORIZON_RESEARCH_ONLY")
        self.assertEqual(result["symbols"][0]["short"]["state"],
                         "RESEARCH_FIT_NOT_ACTIONABLE")
        self.assertEqual(result["symbols"][0]["medium"]["state"],
                         "RESEARCH_FIT_NOT_ACTIONABLE")
        self.assertEqual(result["horizons"]["short"], "3_TO_5_TRADING_SESSIONS")
        self.assertEqual(result["horizons"]["medium"], "1_TO_3_CALENDAR_MONTHS")
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["executable_candidates"], [])
        self.assertFalse(result["buy_recommendations_authorized"])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_short_rejected_does_not_automatically_become_medium(self):
        short = copy.deepcopy(SHORT)
        short["volume_expansion_confirmed"] = False
        medium = copy.deepcopy(MEDIUM)
        medium["valuation_margin_confirmed"] = False
        result = assess(input_for(short, medium))["symbols"][0]
        self.assertEqual(result["category"], "D_NO_VERIFIED_RESEARCH_FIT")
        self.assertEqual(result["short"]["state"], "RESEARCH_RISK_REJECTED")
        self.assertEqual(result["medium"]["state"], "RESEARCH_RISK_REJECTED")

    def test_independent_A_and_B_categories(self):
        med = copy.deepcopy(MEDIUM)
        med["fundamental_improvement_confirmed"] = False
        self.assertEqual(assess(input_for(medium=med))["symbols"][0]["category"],
                         "A_SHORT_RESEARCH_ONLY")
        short = copy.deepcopy(SHORT)
        short["sector_leadership_confirmed"] = False
        self.assertEqual(assess(input_for(short=short))["symbols"][0]["category"],
                         "B_MEDIUM_RESEARCH_ONLY")

    def test_fee_inclusive_short_risk_bounds(self):
        short = copy.deepcopy(SHORT)
        short["net_risk_reward_ratio"] = "1.99"
        short["planned_net_portfolio_loss_fraction"] = "0.0301"
        row = assess(input_for(short=short))["symbols"][0]
        self.assertEqual(row["short"]["state"], "RESEARCH_RISK_REJECTED")
        self.assertIn("NET_RISK_REWARD_BELOW_2_TO_1", row["short"]["reasons"])
        self.assertIn("PLANNED_NET_PORTFOLIO_RISK_EXCEEDS_3_PERCENT",
                      row["short"]["reasons"])
        self.assertEqual(row["category"], "B_MEDIUM_RESEARCH_ONLY")

    def test_future_evidence_and_missing_middle_term_financial_review(self):
        medium = copy.deepcopy(MEDIUM)
        medium["published_on"] = "2026-11-11"
        medium.pop("debt_and_liquidity_risk_reviewed")
        row = assess(input_for(medium=medium))["symbols"][0]
        self.assertEqual(row["medium"]["state"], "EVIDENCE_INCOMPLETE")
        self.assertIn("FUTURE_DATED_EVIDENCE_REJECTED", row["medium"]["reasons"])
        self.assertEqual(row["category"], "A_SHORT_RESEARCH_ONLY")

    def test_no_unverified_st_or_halt_admission(self):
        guard = copy.deepcopy(GUARD)
        guard["official_pit_mainboard_non_st_confirmed"] = False
        result = assess(input_for(guard=guard))["symbols"][0]
        self.assertEqual(result["category"], "D_NO_VERIFIED_RESEARCH_FIT")
        self.assertEqual(result["short"]["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(result["medium"]["state"], "EVIDENCE_INCOMPLETE")

    def test_disallow_chuangye_st_bei_and_non_mainboard(self):
        for code in ("sz.300015", "sz.301015", "sh.688123", "bj.830000",
                     "sz.002249x"):
            data = input_for()
            data["symbols"][0]["issuer"] = code
            row = assess(data)["symbols"][0]
            self.assertEqual(row["category"], "D_REJECTED")
            self.assertEqual(row["short"]["state"], "RESEARCH_RISK_REJECTED")

    def test_no_exec_proof_claims_or_missing_plan_guessed(self):
        data = input_for()
        data["symbols"][0]["short"]["fresh_executable_quotes"] = True
        row = assess(data)["symbols"][0]
        self.assertEqual(row["short"]["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(row["category"], "B_MEDIUM_RESEARCH_ONLY")
        del data["symbols"][0]["medium"]
        row = assess(data)["symbols"][0]
        self.assertEqual(row["category"], "D_NO_VERIFIED_RESEARCH_FIT")

    def test_bad_dates_duplicate_symbols_and_nonfinite_risk_rejected(self):
        data = input_for()
        data["symbols"].append(copy.deepcopy(data["symbols"][0]))
        with self.assertRaisesRegex(ValueError, "duplicated"):
            assess(data)
        data = input_for()
        data["symbols"][0]["short"]["net_risk_reward_ratio"] = "NaN"
        row = assess(data)["symbols"][0]
        self.assertEqual(row["short"]["state"], "EVIDENCE_INCOMPLETE")
        data = input_for()
        data["asof"] = "2026-11-10T15:00:00"
        with self.assertRaises(ValueError):
            assess(data)

    def test_no_global_market_scan_or_trade_authorization(self):
        data = input_for()
        data["symbols"][0]["issuer"] = "sh.600000"
        result = assess(data)
        self.assertTrue(result["categories_are_not_buy_recommendations"])
        self.assertFalse(result["historical_PIT_verified"])
        self.assertFalse(result["realtime_execution_verified"])
        self.assertTrue(result["short_cannot_fallback_to_medium"])
        self.assertEqual(result["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
