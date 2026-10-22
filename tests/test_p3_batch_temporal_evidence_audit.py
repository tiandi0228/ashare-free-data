import unittest
from collector.p3_batch_temporal_evidence_audit import audit_batch

class BatchTemporalAuditTests(unittest.TestCase):
    def test_mixed_issuer_signals_keep_original_time_gate(self):
        items=[
          {"issuer":"sh.603014","signal_date":"2025-05-19","sources":[
            {"source_id":"ipo","original_bytes_verified":True,"listing_day_text_verified":True,
             "acquired_at_utc":"2026-10-22T07:21:52+00:00",
             "historic_PIT_publication_verified":False,"historical_ipo_notice_verified":False}]},
          {"issuer":"sh.600421","signal_date":"2026-06-22","sources":[
            {"source_id":"announcement","original_bytes_verified":True,"listing_day_text_verified":True,
             "acquired_at_utc":"2026-10-22T07:21:52+00:00",
             "historic_PIT_publication_verified":False,"historical_ipo_notice_verified":False}]}
        ]
        q=audit_batch(items)
        self.assertEqual(q["issuer_day_requests"],2)
        self.assertEqual(q["totals"]["ineligible_sources"],2)
        self.assertEqual(q["totals"]["eligible_sources"],0)
        self.assertEqual(q["trade_gate"],"BLOCKED")
        self.assertTrue(all(not r["issuer_full_state_history_certified"] for r in q["results"]))
    def test_duplicates_and_missing_evidence_rejected(self):
        a={"issuer":"sh.603014","signal_date":"2025-05-19","sources":[{"source_id":"x"}]}
        with self.assertRaisesRegex(ValueError,"duplicate issuer"):
            audit_batch([a,a])
        with self.assertRaisesRegex(ValueError,"missing source"):
            audit_batch([{**a,"sources":[]}])
        with self.assertRaisesRegex(ValueError,"duplicate source"):
            audit_batch([{**a,"sources":[{"source_id":"x"},{"source_id":"x"}]}])
    def test_positive_source_never_unlocks_trade(self):
        q=audit_batch([{"issuer":"sh.600001","signal_date":"2025-05-19","sources":[
           {"source_id":"x","original_bytes_verified":True,"listing_day_text_verified":True,
            "acquired_at_utc":"2025-05-01T00:00:00+00:00",
            "historic_PIT_publication_verified":True,"historical_ipo_notice_verified":True}]}])
        self.assertEqual(q["totals"]["eligible_sources"],1)
        self.assertEqual(q["trade_gate"],"BLOCKED")
        self.assertFalse(q["results"][0]["issuer_full_state_history_certified"])
if __name__=="__main__":unittest.main()
