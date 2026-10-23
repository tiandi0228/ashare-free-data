import unittest
from collector.p3_publication_asof_gate import assess

class PublicationAsOfTests(unittest.TestCase):
    def sample(self):
        return {"issuer":"sh.600421","kind":"DELIST_EFFECTIVE",
                "original_sha256":"a"*64,"effective_date":"2026-10-20",
                "authenticated_first_published_at":"2026-10-19T08:00:00+08:00",
                "publisher_independently_authenticated":True,
                "original_bytes_verified":True,
                "publication_timestamp_independently_authenticated":True,
                "trade_gate":"BLOCKED","orders":[]}
    def test_authenticated_prior_publication(self):
        r=assess([self.sample()],"2026-10-20T09:30:00+08:00")
        self.assertEqual(r["known_event_count"],1)
        self.assertTrue(r["events"][0]["effective_by_decision_date"])
        self.assertFalse(r["complete_historical_risk_state"])
    def test_effective_date_uses_exchange_local_day(self):
        a=self.sample()
        a["effective_date"]="2026-10-20"
        a["authenticated_first_published_at"]="2026-10-19T10:00:00+08:00"
        r=assess([a],"2026-10-20T00:30:00+08:00")
        self.assertTrue(r["events"][0]["effective_by_decision_date"])
        self.assertEqual(r["decision_instant_utc"],"2026-10-19T16:30:00+00:00")
        before=assess([a],"2026-10-19T23:30:00+08:00")
        self.assertFalse(before["events"][0]["effective_by_decision_date"])

    def test_executable_candidate_cannot_pass_event_gate(self):
        a=self.sample();a["executable_candidates"]=[{"code":"sh.600421"}]
        with self.assertRaisesRegex(ValueError,"risk boundary"):
            assess([a],"2026-10-20T09:30:00+08:00")

    def test_future_publication_cannot_look_back(self):
        a=self.sample()
        a["authenticated_first_published_at"]="2026-10-20T17:00:00+08:00"
        r=assess([a],"2026-10-20T09:30:00+08:00")
        self.assertEqual(r["known_event_count"],0)
    def test_scrape_timestamp_not_authenticated(self):
        a=self.sample();a["publication_timestamp_independently_authenticated"]=False
        self.assertFalse(assess([a],"2026-10-20T09:30:00+08:00")["events"][0]["known_before_decision"])
    def test_missing_timezone_rejected(self):
        with self.assertRaises(ValueError):assess([self.sample()],"2026-10-20T09:30:00")
    def test_wrong_digest_rejected(self):
        a=self.sample();a["original_sha256"]="invalid"
        with self.assertRaises(ValueError):assess([a],"2026-10-20T09:30:00+08:00")
if __name__=="__main__":unittest.main()
