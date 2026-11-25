import unittest

from collector.p2_coverage_display import summarize


class CoverageDisplayTest(unittest.TestCase):
    def setUp(self):
        safe = dict(trade_gate="BLOCKED", orders=[], historical_PIT_verified=False, source_epoch_sha256="x")
        self.coverage = dict(safe, status="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
                             feature_complete_shards=270, observed_archived_shards=289,
                             observed_with_feature_gaps_shards=19, feature_issuer_count=2286,
                             observed_feature_or_gap_issuers=2306, issuer_evidence_gap_count=20,
                             unobserved_archived_shards=0, gap_issuer_codes=[str(n) for n in range(20)])
        self.disp = dict(safe, asof="2026-10-20", feature_gaps_resolved=0,
                         explained_feature_unavailable=20, review_required=0, rows=[
                             dict(issuer=str(n), reason="VENDOR_REASON",
                                  status="EXPLAINED_FEATURE_UNAVAILABLE") for n in range(20)])

    def test_two_denominators_and_no_promotions(self):
        r = summarize(self.coverage, self.disp)
        self.assertEqual(r["feature_complete_shards"], dict(count=270, total=289, percent=93.43))
        self.assertEqual(r["computed_feature_issuers"], dict(count=2286, total=2306, percent=99.13))
        self.assertEqual((r["explained_uncomputable_issuers"], r["feature_gaps_resolved"]), (20, 0))

    def test_duplicate_issuer_or_counter_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            summarize({**self.coverage, "feature_complete_shards": 269}, self.disp)
        self.disp["rows"][0]["issuer"] = "1"
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            summarize(self.coverage, self.disp)

    def test_unexplained_is_not_counted_as_explained(self):
        self.disp.update(explained_feature_unavailable=19, review_required=1)
        self.disp["rows"][0].update(status="REVIEW_REQUIRED", reason=None)
        r = summarize(self.coverage, self.disp)
        self.assertEqual((r["explained_uncomputable_issuers"], r["unexplained_issuers_requiring_review"]), (19, 1))
