import unittest
from collector.p4_sse_live_notice_receipts import capture
class Tests(unittest.TestCase):
    def test_mock_official_receipt(self):
        def fetch(url):return b"official-host-HTML-not-yet-parsed",url,200
        r=capture(fetch)
        self.assertEqual(r["fetched_count"],3)
        self.assertEqual(len(r["receipts"][0]["sha256"]),64)
        self.assertFalse(r["historical_exchange_calendar_authenticated"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_failure_fail_closed(self):
        def fail(url):raise OSError("network unavailable")
        r=capture(fail)
        self.assertEqual(r["fetched_count"],0)
        self.assertTrue(all(x["status"]=="SOURCE_UNAVAILABLE" for x in r["receipts"]))
    def test_redirect_to_untrusted_host_rejected(self):
        def evil(url):return b"x","https://evil.example/article",200
        self.assertEqual(capture(evil)["fetched_count"],0)
if __name__=="__main__":unittest.main()
