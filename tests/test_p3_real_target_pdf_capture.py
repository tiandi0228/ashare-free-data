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
    def test_star_st_title_is_prioritized_as_research_only(self):
        report=self.sample()
        report["results"][0]["candidates"][0]["announcement_title_unverified"]="关于公司经营情况的公告"
        report["results"][0]["candidates"].append({
            "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-01-03/123456791.PDF",
            "announcement_id":"123456791","announcement_title_unverified":"关于实施*ST风险警示的公告",
            "historical_PIT_verified":False})
        chosen=choose(report)
        self.assertEqual(chosen[0]["announcement_id"],"123456791")
        self.assertEqual(chosen[0]["selection_reason"],"RISK_TITLE_RESEARCH_PRIORITY")
    def test_decision_date_filters_out_postdated_risk_notice(self):
        report=self.sample()
        first=report["results"][0]["candidates"][0]
        first["announcement_title_unverified"]="关于股票停牌的公告"
        first["official_pdf_url"]="https://static.cninfo.com.cn/finalpage/2026-10-26/123456789.PDF"
        report["results"][0]["candidates"].append({
            "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-10-19/123456790.PDF",
            "announcement_id":"123456790","announcement_title_unverified":"上市公司公告",
            "historical_PIT_verified":False})
        scout={"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
               "trade_gate":"BLOCKED","official_PIT_verified":False,
               "targets":[{"issuer":"sz.000001","observed_decision_dates":["2026-10-20"]}]}
        picked=choose(report,scout=scout)[0]
        self.assertEqual(picked["announcement_id"],"123456790")
        self.assertTrue(picked["could_precede_target_decision_day_unverified"])
        self.assertFalse(picked["first_publication_time_authenticated"])
    def test_prioritize_halt_transition_over_recent_generic_date(self):
        report=self.sample()
        report["results"][0]["candidates"][0]["announcement_title_unverified"]="经营情况说明"
        report["results"][0]["candidates"][0]["official_pdf_url"]="https://static.cninfo.com.cn/finalpage/2026-10-19/123456789.PDF"
        report["results"][0]["candidates"].append({
            "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-09-13/123456790.PDF",
            "announcement_id":"123456790","announcement_title_unverified":"关于股票停牌公告",
            "historical_PIT_verified":False})
        scout={"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
               "trade_gate":"BLOCKED","official_PIT_verified":False,
               "targets":[{"issuer":"sz.000001","observed_decision_dates":["2026-09-14","2026-10-20"],
                           "vendor_halt_transition_research_days":["2026-09-14"],
                           "vendor_suspended_research_days":["2026-09-14"]}]}
        self.assertEqual(choose(report,scout=scout)[0]["announcement_id"],"123456790")
    def test_vendor_transition_not_in_source_scope_rejected(self):
        scout={"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
               "trade_gate":"BLOCKED","official_PIT_verified":False,
               "targets":[{"issuer":"sz.000001","observed_decision_dates":["2026-10-20"],
                           "vendor_halt_transition_research_days":["2026-09-14"]}]}
        with self.assertRaises(ValueError):choose(self.sample(),scout=scout)
    def test_frozen_scope_mismatch_fails_closed(self):
        scout={"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
               "trade_gate":"BLOCKED","official_PIT_verified":False,
               "targets":[{"issuer":"sh.600000","observed_decision_dates":["2026-10-20"]}]}
        with self.assertRaises(ValueError):choose(self.sample(),scout=scout)
    def test_reject_untrusted_url(self):
        r=self.sample();r["results"][0]["candidates"][0]["official_pdf_url"]="https://evil.invalid/x.pdf"
        with self.assertRaises(ValueError):choose(r)
    def test_failure_is_not_negative_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            q=capture(self.sample(),d,fetch=lambda _:b"bad")
            self.assertEqual(q["retrieved"],0)
            self.assertEqual(q["sources"][0]["status"],"UNAVAILABLE_NOT_NO_RISK")
if __name__=="__main__":unittest.main()
