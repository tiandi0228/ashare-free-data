import unittest
from collector.p3_positive_effective_text_candidates import check_text

class PositiveEventTextTests(unittest.TestCase):
    def test_direct_explicit_halt_and_resume(self):
        self.assertEqual(check_text("TRADING_HALT","2025年12月31日","公司股票自2025年12月31日起停牌")["candidate"],"HALT_START")
        self.assertEqual(check_text("TRADING_HALT","2026年1月5日","公司股票于2026年1月5日起复牌")["candidate"],"RESUME_START")
    def test_unrelated_date_cannot_activate(self):
        self.assertIsNone(check_text("TRADING_HALT","2026年1月5日","2026年1月5日披露停牌公告")["candidate"])
    def test_st_subtype_and_forecast(self):
        self.assertEqual(check_text("ST_CHANGE","2025年7月4日","公司股票自2025年7月4日起撤销退市风险警示")["candidate"],"ST_WARNING_REMOVED")
        self.assertIsNone(check_text("DELIST_RISK_ISSUER_FORECAST","2026年6月22日","预计2026年6月22日最后交易")["candidate"])
    def test_multiple_directions_fail_closed(self):
        q=check_text("TRADING_HALT","2026年1月5日","于2026年1月5日起停牌；于2026年1月5日起复牌")
        self.assertIsNone(q["candidate"])
if __name__=="__main__":unittest.main()
