import unittest
from collector.p4_residual_notice_pdf import verify,event_date_matches
class PdfTests(unittest.TestCase):
    def test_match(self):
        self.assertTrue(verify("证券代码002861。股票交易异常波动。2026年11月11日收盘价格涨幅偏离值。","sz.002861","2026-11-11"))
    def test_signature_date(self):
        self.assertFalse(verify("证券代码002861。股票交易异常波动。董事会2026年11月11日。","sz.002861","2026-11-11"))
    def test_other_issuer(self):
        self.assertFalse(verify("证券代码002862。股票交易异常波动。11月11日收盘涨幅。","sz.002861","2026-11-11"))
    def test_wrong_day(self):
        self.assertFalse(event_date_matches("11月12日股票交易异常波动。","2026-11-11"))
