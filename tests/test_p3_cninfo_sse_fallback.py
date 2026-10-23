import unittest
from collector.p3_cninfo_sse_fallback import assess
class FallbackTests(unittest.TestCase):
    def test_independent_sse_does_not_certify_missing_cninfo(self):
        idx={"trade_gate":"BLOCKED","historical_PIT_eligible":0,"unavailable_or_unmatched":[{"source_id":"cninfo_600421_risk_20260619"}]}
        sse={"trade_gate":"BLOCKED","historical_point_in_time_universe_verified":False,"issuer":"sh.600421","attempted_gets":2,
             "page_events":[{"status":"OBSERVED_OFFICIAL_HOST_UNVERIFIED_PUBLICATION_TIMING","event":"DELIST_DECISION_ONLY"},{"status":"OBSERVED_OFFICIAL_HOST_UNVERIFIED_PUBLICATION_TIMING","event":"DELIST_EFFECTIVE_DATE_ANNOUNCED"}]}
        r=assess(idx,sse)
        self.assertEqual(r["sse_official_host_events_observed"],2)
        self.assertFalse(r["cninfo_missing_id_resolved"])
        self.assertFalse(r["historical_first_publication_authenticated"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
