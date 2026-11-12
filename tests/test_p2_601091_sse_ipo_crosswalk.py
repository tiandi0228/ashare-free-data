"""Fail-closed SSE IPO provenance binding and non-fabricated feature-window tests."""
import unittest
from collector.p2_601091_sse_ipo_crosswalk import crosswalk, SSE_NOTICE, ORIGINAL_SHA
from collector.p2_original_gap_action_triage import triage
from tests.test_p2_original_gap_action_triage import fixture

def source():
    raw=fixture()
    record=raw["gap_repair_queue"][3]["issuer_reasons"][0]
    record["issuer"]="sh.601091"
    record["original_gap_diagnostic"]["original_csv_sha256"]=ORIGINAL_SHA
    return triage(raw)

class IPOCrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.p=source()
    def reject(self):
        with self.assertRaises(ValueError):crosswalk(self.p)

    def test_exact_official_listing_day_binds_to_first_vendor_day(self):
        result=crosswalk(self.p)
        self.assertEqual(result["source_reference"]["listed_first_day"],"2026-09-17")
        self.assertEqual(result["vendor_first_observed_row_day"],"2026-09-17")
        self.assertEqual(result["source_reference"]["official_url"],SSE_NOTICE)
        self.assertEqual(result["vendor_observed_rows"],18)
        self.assertEqual(result["observed_vendor_row_shortfall"],3)
        self.assertFalse(result["gap_resolved"])
        self.assertEqual(result["feature_complete_shards_promoted"],0)
        self.assertFalse(result["historical_prelisting_bars_permitted"])
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_other_15_halt_gaps_unchanged(self):
        r=crosswalk(self.p)
        self.assertEqual(len(self.p["research_actions"]),16)
        self.assertEqual(len([x for x in self.p["research_actions"]
                if x["category"]=="VENDOR_SUSPENDED_IN_LAST_21_ROWS"]),15)
        self.assertFalse(r["daily_tradability_status_certified"])

    def test_forged_source_sha_rejected(self):
        self.p["research_actions"][4]["original_csv_sha256"]="a"*64
        self.reject()

    def test_wrong_shard_rejected(self):
        self.p["research_actions"][4]["shard_id"]="shard_0098"
        self.reject()

    def test_forged_gap_resolved_rejected(self):
        self.p["research_actions"][4]["gap_resolved"]=True
        self.reject()

    def test_forged_feature_promotion_rejected(self):
        self.p["research_actions"][4]["eligible_for_feature_complete_promotion"]=True
        self.reject()

    def test_missing_ipo_rejected(self):
        self.p["research_actions"][4]["issuer"]="sh.601092"
        self.reject()

    def test_fake_pit_certification_rejected(self):
        self.p["historical_PIT_verified"]=True
        self.reject()

    def test_open_trade_gate_rejected(self):
        self.p["trade_gate"]="OPEN"
        self.reject()

    def test_duplicate_ipo_rejected(self):
        self.p["research_actions"][0]["issuer"]="sh.601091"
        self.reject()
