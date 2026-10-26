import tempfile,unittest,hashlib
from pathlib import Path
from collector.p3_real_target_pdf_capture import capture,choose
class TestLiveCapture(unittest.TestCase):
    def sample(self):
        return {"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY","trade_gate":"BLOCKED",
        "results":[{"issuer":"sz.000001","candidates":[{"official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-01-01/123456789.PDF",
          "announcement_id":"123456789","historical_PIT_verified":False}]}]}
    def test_original_hash_is_not_pit(self):
        with tempfile.TemporaryDirectory() as d:
            raw=b"%PDF-"+b"z"*3100
            q=capture(self.sample(),d,fetch=lambda _:raw)
            self.assertEqual(q["retrieved"],1)
            self.assertEqual(q["sources"][0]["sha256"],hashlib.sha256(raw).hexdigest())
            self.assertFalse(q["historical_PIT_verified"])
            self.assertTrue((Path(d)/q["sources"][0]["original_file"]).exists())
    def test_relevant_original_title_before_generic_first_notice(self):
        report=self.sample()
        candidate=report["results"][0]["candidates"][0]
        candidate["announcement_title_unverified"]="第三季度经营情况公告"
        report["results"][0]["candidates"].append({
            "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-01-02/123456790.PDF",
            "announcement_id":"123456790","announcement_title_unverified":"关于股票停牌的公告",
            "historical_PIT_verified":False})
        chosen=choose(report)
        self.assertEqual(chosen[0]["announcement_id"],"123456790")
        self.assertEqual(chosen[0]["selection_reason"],"RISK_TITLE_RESEARCH_PRIORITY")
    def test_no_risk_keyword_is_fallback_not_certified(self):
        r=choose(self.sample())
        self.assertEqual(r[0]["selection_reason"],"INDEX_ORDER_FALLBACK")
    def test_reject_untrusted_url(self):
        r=self.sample();r["results"][0]["candidates"][0]["official_pdf_url"]="https://evil.invalid/x.pdf"
        with self.assertRaises(ValueError):choose(r)
    def test_failure_is_not_negative_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            q=capture(self.sample(),d,fetch=lambda _:b"bad")
            self.assertEqual(q["retrieved"],0)
            self.assertEqual(q["sources"][0]["status"],"UNAVAILABLE_NOT_NO_RISK")
if __name__=="__main__":unittest.main()
