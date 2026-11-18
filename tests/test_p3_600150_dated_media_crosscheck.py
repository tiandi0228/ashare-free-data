"""Tests for dated-media evidence boundary, not official publication authentication."""
import unittest
from collector.p3_600150_dated_media_crosscheck import build, PINNED


class DatedMediaEvidenceTests(unittest.TestCase):
    def test_two_expected_notice_ids(self):
        self.assertEqual(set(PINNED), {"1224387134", "1224504273"})

    def test_only_research_dates(self):
        result = build()
        self.assertEqual(result["historical_notice_days_crossreferenced"], 2)
        self.assertEqual(result["independently_authenticated_first_publication_instants"], 0)

    def test_no_trade_promotion(self):
        result = build()
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertEqual(result["executable_candidates"], [])
        self.assertFalse(result["official_historical_PIT_verified"])

    def test_exact_halt_and_resume_dates(self):
        rows = {r["announcement_id"]: r for r in build()["rows"]}
        self.assertEqual(rows["1224387134"]["effective_date_claim_from_issuer_notice"], "2025-08-13")
        self.assertEqual(rows["1224504273"]["effective_date_claim_from_issuer_notice"], "2025-08-19")

    def test_unverified_certification_flags(self):
        for row in build()["rows"]:
            for key in (
                "publication_time_of_day_authenticated",
                "publisher_origin_independently_authenticated",
                "exchange_effective_interval_authenticated",
                "complete_historical_PIT_state_authenticated",
                "candidate_asof_trade_eligible",
            ):
                self.assertIs(row[key], False)

    def test_required_missing_evidence(self):
        for row in build()["rows"]:
            self.assertEqual(len(row["remaining_evidence"]), 4)

    def test_distinct_media_and_index_sources(self):
        for row in build()["rows"]:
            self.assertIn("epaper.cs.com.cn", row["dated_media_evidence_url"])
            self.assertIn("sina.com.cn", row["secondary_notice_index_url"])
            self.assertNotEqual(row["dated_media_evidence_url"], row["secondary_notice_index_url"])
