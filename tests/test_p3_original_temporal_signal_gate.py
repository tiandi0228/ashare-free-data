import unittest
from collector.p3_original_temporal_signal_gate import classify

class TemporalGateTests(unittest.TestCase):
    def test_current_capture_of_2025_notice_cannot_be_used_in_2025(self):
        rec={"sources":[{"source_id":"cninfo_ipo","original_bytes_verified":True,
                         "listing_day_text_verified":True,
                         "acquired_at_utc":"2026-10-22T07:21:52+00:00",
                         "historic_PIT_publication_verified":False,
                         "historical_ipo_notice_verified":False}]}
        out=classify(rec,"2025-05-19")
        self.assertEqual(out["eligible_sources"],[])
        self.assertIn("ACQUIRED_AFTER_SIGNAL_DAY",out["ineligible_sources"][0]["reasons"])
        self.assertEqual(out["trade_gate"],"BLOCKED")
        later=classify(rec,"2026-10-23")
        self.assertFalse(later["source_eligible_for_historical_signal"])
        self.assertIn("HISTORICAL_PUBLICATION_INSTANT_UNVERIFIED",later["ineligible_sources"][0]["reasons"])
    def test_missing_or_naive_timestamps_fail_closed(self):
        rec={"sources":[{"source_id":"x","original_bytes_verified":True,
                         "listing_day_text_verified":True,"acquired_at_utc":"2025-05-01T10:00:00"}]}
        with self.assertRaisesRegex(ValueError,"naive"):
            classify(rec,"2025-05-19")
        rec["sources"][0].pop("acquired_at_utc")
        self.assertIn("MISSING_ACQUISITION_TIME",classify(rec,"2025-05-19")["ineligible_sources"][0]["reasons"])
    def test_verified_single_issuer_never_unblocks_full_market_trading(self):
        rec={"sources":[{"source_id":"x","original_bytes_verified":True,"listing_day_text_verified":True,
                         "acquired_at_utc":"2025-05-01T00:00:00+00:00",
                         "historic_PIT_publication_verified":True,"historical_ipo_notice_verified":True}]}
        out=classify(rec,"2025-05-19")
        self.assertEqual(len(out["eligible_sources"]),1)
        self.assertEqual(out["trade_gate"],"BLOCKED")
        self.assertFalse(out["historical_full_market_universe_certified"])
if __name__=="__main__":unittest.main()
