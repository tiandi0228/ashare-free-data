import unittest
from collector.p3_publication_time_provenance_gate import audit
class PublicationTests(unittest.TestCase):
    def sample(self):
        return {"phase":"P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE","trade_gate":"BLOCKED",
          "sources":[{"PIT_publication_verified":False,"authenticated_first_published_at":None,
            "http_headers_prove_first_publication":False,"original_bytes_verified":True,
            "observed_at_utc":"2026-10-25T12:00:00Z","sha256":"a"*64}]}
    def test_retrieval_is_not_publication(self):
        self.assertEqual(audit(self.sample())["historical_PIT_eligible"],0)
    def test_reject_fabricated_first_publication(self):
        x=self.sample();x["sources"][0]["authenticated_first_published_at"]="2025-01-01T00:00:00Z"
        with self.assertRaises(ValueError):audit(x)
    def test_reject_http_header_promotion(self):
        x=self.sample();x["sources"][0]["http_headers_prove_first_publication"]=True
        with self.assertRaises(ValueError):audit(x)
    def test_invalid_verified_original_receipts_fail_closed(self):
        changes=(
            ("sha256","not-a-sha"),
            ("sha256","A"*64),
            ("observed_at_utc","2026-10-25T12:00:00"),
            ("observed_at_utc","invalid"),
            ("observed_at_utc",None),
            ("original_bytes_verified",None),
        )
        for key,value in changes:
            with self.subTest(field=key,value=value):
                x=self.sample();x["sources"][0][key]=value
                with self.assertRaises(ValueError):audit(x)

    def test_reject_malformed_sources_and_accept_timezone_offset(self):
        for invalid in (None,{},[None],[]):
            x=self.sample();x["sources"]=invalid
            with self.assertRaises(ValueError):audit(x)
        x=self.sample()
        x["sources"][0]["observed_at_utc"]="2026-10-25T20:00:00+08:00"
        result=audit(x)
        self.assertEqual(result["retrieval_observations"],1)
        self.assertEqual(result["historical_PIT_eligible"],0)
        self.assertEqual(result["trade_gate"],"BLOCKED")

if __name__=="__main__":unittest.main()
