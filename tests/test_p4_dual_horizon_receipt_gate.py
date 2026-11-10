import copy
import hashlib
import unittest

from collector.p4_dual_horizon_receipt_gate import inspect


def receipt(scope, indicator, value, day="2026-11-09",
            source_type="exchange_disclosure", text="source text"):
    if scope == "universe":
        source_type = "exchange_security_status"
    return {
        "scope": scope, "indicator": indicator, "value": value,
        "source_type": source_type,
        "source_ref": "https://example.test/receipt",
        "published_on": day, "source_excerpt": text,
        "source_excerpt_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def packet(records):
    return {"asof": "2026-11-10",
            "symbols": [{"issuer": "sz.000069", "receipts": records}]}


class DualHorizonReceiptGateTests(unittest.TestCase):
    def test_empty_evidence_cannot_create_a_buy_signal(self):
        result = inspect(packet([]))
        self.assertEqual(result["evaluated_symbols"], 1)
        self.assertEqual(result["receipts_sha_checked"], 0)
        self.assertEqual(result["eligible_buy_candidates"], [])
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["trade_gate"], "BLOCKED")
        sym = result["provisional_assertion_only_assessment"]["symbols"][0]
        self.assertEqual(sym["category"], "D_NO_VERIFIED_RESEARCH_FIT")
        self.assertEqual(sym["short"]["state"], "EVIDENCE_INCOMPLETE")
        self.assertFalse(result["source_authenticity_verified"])

    def test_partial_independent_lanes_dont_infer_missing_fundamentals(self):
        rows = [
            receipt("universe", "official_pit_mainboard_non_st_confirmed", True),
            receipt("universe", "no_suspension_confirmed", True),
            receipt("short", "price_structure_confirmed", True,
                    source_type="vendor_bar"),
            receipt("medium", "fundamental_improvement_confirmed", True,
                    source_type="financial_report"),
        ]
        result = inspect(packet(rows))
        sym = result["provisional_assertion_only_assessment"]["symbols"][0]
        self.assertEqual(sym["category"], "D_NO_VERIFIED_RESEARCH_FIT")
        self.assertEqual(sym["short"]["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(sym["medium"]["state"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(result["receipts_sha_checked"], 4)

    def test_tampered_excerpt_rejected(self):
        row = receipt("short", "volume_expansion_confirmed", True)
        row["source_excerpt"] = "changed"
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            inspect(packet([row]))

    def test_stale_short_and_medium_are_independently_rejected(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            inspect(packet([receipt("short", "volume_expansion_confirmed", True,
                                    day="2026-10-20")]))
        with self.assertRaisesRegex(ValueError, "stale"):
            inspect(packet([receipt("medium", "financial_health_reviewed", True,
                                    day="2026-06-01")]))

    def test_unknown_dates_future_and_unknown_source_fail_closed(self):
        for bad_date in ("2026-11-11", "2026-11-09T12:00:00"):
            with self.subTest(bad_date=bad_date), self.assertRaises(ValueError):
                inspect(packet([receipt("medium", "financial_health_reviewed",
                                        True, day=bad_date)]))
        row = receipt("medium", "financial_health_reviewed", True)
        row["source_type"] = "social_rumor"
        with self.assertRaisesRegex(ValueError, "source type"):
            inspect(packet([row]))

    def test_duplicate_and_cross_horizon_claims_rejected(self):
        row = receipt("short", "volume_expansion_confirmed", True)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            inspect(packet([row, copy.deepcopy(row)]))
        row = receipt("medium", "volume_expansion_confirmed", True)
        with self.assertRaisesRegex(ValueError, "cross-horizon"):
            inspect(packet([row]))

    def test_official_status_requires_independent_source_type(self):
        row = receipt("universe", "no_suspension_confirmed", True)
        row["source_type"] = "valuation_research"
        with self.assertRaisesRegex(ValueError, "security-status"):
            inspect(packet([row]))

    def test_bad_numeric_risk_and_boolean_assertions_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            inspect(packet([receipt("short", "net_risk_reward_ratio", "NaN")]))
        with self.assertRaisesRegex(ValueError, "explicit true/false"):
            inspect(packet([receipt("medium", "valuation_margin_confirmed", "yes")]))

    def test_provenance_integrity_is_not_source_authentication(self):
        rows = [receipt("universe", "official_pit_mainboard_non_st_confirmed", True),
                receipt("universe", "no_suspension_confirmed", True)]
        from collector.p4_dual_horizon_research import SHORT, MEDIUM
        for name in SHORT:
            rows.append(receipt("short", name, True, source_type="vendor_bar"))
        rows.extend([
            receipt("short", "net_risk_reward_ratio", "2.5"),
            receipt("short", "planned_net_portfolio_loss_fraction", "0.02"),
        ])
        for name in MEDIUM:
            rows.append(receipt("medium", name, True, source_type="financial_report"))
        for name in ("debt_and_liquidity_risk_reviewed",
                     "earnings_event_risk_reviewed", "fundamental_invalidation_defined"):
            rows.append(receipt("medium", name, True, source_type="financial_report"))
        rows.append(receipt("medium", "stress_drawdown_fraction", "0.10"))
        result = inspect(packet(rows))
        provisional = result["provisional_assertion_only_assessment"]["symbols"][0]
        self.assertEqual(provisional["category"], "C_DUAL_HORIZON_RESEARCH_ONLY")
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["semantic_claims_independently_verified"])
        self.assertFalse(result["official_pit_universe_certified"])
        self.assertEqual(result["eligible_buy_candidates"], [])
        self.assertEqual(result["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
