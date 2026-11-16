import unittest
from collector.p2_gap_disposition import compare


class GapDispositionTests(unittest.TestCase):
    def setUp(self):
        item = dict(source_shard="shard_0001", original_csv_sha256="a" * 64,
                    diagnosis="FEWER_THAN_21_VENDOR_ROWS_ASOF",
                    available_vendor_rows_through_asof=18, trailing_vendor_suspended_rows=0)
        self.p = dict(asof="2026-10-20", source_epoch_sha256="x", entries={"sh.601091": item.copy()})
        self.r = dict(phase="P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS",
                      status="SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY", trade_gate="BLOCKED",
                      orders=[], executable_candidates=[], historical_PIT_verified=False,
                      coverage_gaps_resolved=0, research_gap_issuers=1,
                      asof_completed_day="2026-10-20", source_epoch_sha256="x",
                      results=[dict(item, issuer="sh.601091", asof_date="2026-10-20")])

    def test_known_cause_does_not_promote_coverage(self):
        r = compare(self.r, self.p)
        self.assertEqual((r["explained_feature_unavailable"], r["review_required"]), (1, 0))
        self.assertEqual(r["feature_gaps_resolved"], 0)

    def test_epoch_cutoff_and_changed_bytes_do_not_inherit_explanation(self):
        for p in (dict(self.p, asof="2026-10-21"), dict(self.p, source_epoch_sha256="y")):
            self.assertEqual(compare(self.r, p)["review_required"], 1)
        self.r["results"][0]["original_csv_sha256"] = "b" * 64
        self.assertEqual(compare(self.r, self.p)["review_required"], 1)

    def test_promoted_or_duplicate_replay_rejected(self):
        with self.assertRaises(ValueError):
            compare(dict(self.r, coverage_gaps_resolved=1), self.p)
        with self.assertRaises(ValueError):
            compare(dict(self.r, results=self.r["results"] * 2), self.p)
